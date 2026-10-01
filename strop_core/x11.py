"""
X11 and XWayland window positioning and always-on-top (_NET_WM_STATE_ABOVE) helpers.
Robustly discovers toplevel windows via _NET_CLIENT_LIST and XQueryTree recursion,
and sends EWMH client messages to pin windows permanently on top of full-screen games.
"""

import ctypes
from typing import Optional, List


def pin_window_on_top(target_title: str = "Strop HUD Overlay", x: int = 12, y: int = 12) -> bool:
    """
    Finds a window by title substring on X11/XWayland, positions it at (x, y),
    and sends _NET_WM_STATE_ABOVE to pin it permanently above fullscreen/windowed games.
    """
    try:
        x11 = ctypes.cdll.LoadLibrary('libX11.so.6')
        Display_p = ctypes.c_void_p
        Window = ctypes.c_ulong
        Atom = ctypes.c_ulong

        x11.XOpenDisplay.restype = Display_p
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]

        display = x11.XOpenDisplay(None)
        if not display:
            return False

        root = x11.XDefaultRootWindow(display)

        def get_atom(name: str) -> int:
            x11.XInternAtom.restype = Atom
            x11.XInternAtom.argtypes = [Display_p, ctypes.c_char_p, ctypes.c_int]
            return x11.XInternAtom(display, name.encode('ascii'), False)

        net_wm_state = get_atom('_NET_WM_STATE')
        net_wm_state_above = get_atom('_NET_WM_STATE_ABOVE')
        net_wm_state_stays_on_top = get_atom('_NET_WM_STATE_STAYS_ON_TOP')
        net_wm_state_sticky = get_atom('_NET_WM_STATE_STICKY')
        net_client_list = get_atom('_NET_CLIENT_LIST')
        net_wm_name = get_atom('_NET_WM_NAME')
        wm_name = get_atom('WM_NAME')

        def get_window_title(win_id) -> str:
            for atom_type, name_atom in [('UTF8_STRING', net_wm_name), ('STRING', wm_name)]:
                name_type = Atom()
                name_fmt = ctypes.c_int()
                name_nitems = ctypes.c_ulong()
                name_bytes = ctypes.c_ulong()
                name_prop = ctypes.c_void_p()
                
                status = x11.XGetWindowProperty(
                    display, win_id, name_atom, 0, 1024, False,
                    get_atom(atom_type), ctypes.byref(name_type), ctypes.byref(name_fmt),
                    ctypes.byref(name_nitems), ctypes.byref(name_bytes), ctypes.byref(name_prop)
                )
                if status == 0 and name_prop.value:
                    title_str = ctypes.string_at(name_prop.value).decode('utf-8', errors='ignore')
                    x11.XFree(name_prop)
                    if title_str:
                        return title_str
            return ""

        def apply_pin(win_id: int):
            # 1. Position window
            x11.XMoveWindow.argtypes = [Display_p, Window, ctypes.c_int, ctypes.c_int]
            x11.XMoveWindow(display, win_id, x, y)

            # 2. Send _NET_WM_STATE_ABOVE + STICKY client message
            class XClientMessageEvent(ctypes.Structure):
                _fields_ = [
                    ('type', ctypes.c_int),
                    ('serial', ctypes.c_ulong),
                    ('send_event', ctypes.c_int),
                    ('display', ctypes.c_void_p),
                    ('window', ctypes.c_ulong),
                    ('message_type', ctypes.c_ulong),
                    ('format', ctypes.c_int),
                    ('data_l', ctypes.c_ulong * 5),
                ]

            event = XClientMessageEvent()
            event.type = 33  # ClientMessage
            event.serial = 0
            event.send_event = 1
            event.display = display
            event.window = win_id
            event.message_type = net_wm_state
            event.format = 32
            event.data_l[0] = 1  # _NET_WM_STATE_ADD
            event.data_l[1] = net_wm_state_above
            event.data_l[2] = net_wm_state_stays_on_top
            event.data_l[3] = 1  # Source indication: normal application
            event.data_l[4] = 0

            x11.XSendEvent.argtypes = [Display_p, Window, ctypes.c_int, ctypes.c_long, ctypes.c_void_p]
            x11.XSendEvent(display, root, False, (1 << 19) | (1 << 20), ctypes.byref(event))

            # Send sticky event so it stays across virtual workspaces
            event_sticky = XClientMessageEvent()
            event_sticky.type = 33
            event_sticky.serial = 0
            event_sticky.send_event = 1
            event_sticky.display = display
            event_sticky.window = win_id
            event_sticky.message_type = net_wm_state
            event_sticky.format = 32
            event_sticky.data_l[0] = 1  # _NET_WM_STATE_ADD
            event_sticky.data_l[1] = net_wm_state_sticky
            event_sticky.data_l[2] = 0
            event_sticky.data_l[3] = 1
            event_sticky.data_l[4] = 0

            x11.XSendEvent(display, root, False, (1 << 19) | (1 << 20), ctypes.byref(event_sticky))
            x11.XFlush(display)

        # Collect candidate windows from _NET_CLIENT_LIST
        actual_type = Atom()
        actual_format = ctypes.c_int()
        nitems = ctypes.c_ulong()
        bytes_after = ctypes.c_ulong()
        prop = ctypes.c_void_p()

        x11.XGetWindowProperty.restype = ctypes.c_int
        x11.XGetWindowProperty.argtypes = [
            Display_p, Window, Atom, ctypes.c_long, ctypes.c_long, ctypes.c_int,
            Atom, ctypes.POINTER(Atom), ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_void_p)
        ]

        status = x11.XGetWindowProperty(
            display, root, net_client_list, 0, 1024, False,
            get_atom('WINDOW'), ctypes.byref(actual_type), ctypes.byref(actual_format),
            ctypes.byref(nitems), ctypes.byref(bytes_after), ctypes.byref(prop)
        )

        matched = False
        if status == 0 and prop.value:
            win_array = ctypes.cast(prop, ctypes.POINTER(Window))
            for i in range(nitems.value):
                win_id = win_array[i]
                t_str = get_window_title(win_id)
                if target_title.lower() in t_str.lower() or "hud overlay" in t_str.lower() or "strop" in t_str.lower():
                    apply_pin(win_id)
                    matched = True
                    break
            x11.XFree(prop)

        # Fallback: traverse XQueryTree if _NET_CLIENT_LIST didn't match immediately
        if not matched:
            root_return = Window()
            parent_return = Window()
            children_p = ctypes.POINTER(Window)()
            nchildren = ctypes.c_uint()

            x11.XQueryTree.restype = ctypes.c_int
            x11.XQueryTree.argtypes = [
                Display_p, Window, ctypes.POINTER(Window), ctypes.POINTER(Window),
                ctypes.POINTER(ctypes.POINTER(Window)), ctypes.POINTER(ctypes.c_uint)
            ]

            q_status = x11.XQueryTree(
                display, root, ctypes.byref(root_return), ctypes.byref(parent_return),
                ctypes.byref(children_p), ctypes.byref(nchildren)
            )

            if q_status != 0 and children_p:
                for i in range(nchildren.value):
                    c_win = children_p[i]
                    t_str = get_window_title(c_win)
                    if target_title.lower() in t_str.lower() or "hud overlay" in t_str.lower() or "strop" in t_str.lower():
                        apply_pin(c_win)
                        matched = True
                        break
                x11.XFree(children_p)

        x11.XCloseDisplay(display)
        return matched
    except Exception:
        return False
