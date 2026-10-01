# 🧠 Strop Roadmap: AI-Powered Macro Generation & Preset Library

## 🎯 Goal
Allow users to interact with AI models (Google Gemini API, OpenAI ChatGPT API, or Local Offline Ollama) to generate game-specific macro libraries (e.g. Helldivers 2 stratagems, fighting game combos, MMO ability rotations, and OS productivity shortcuts) and directly assign them from the Strop Studio interface.

---

## 🏗️ Architectural Flow

```
                                 ┌──────────────────────────────┐
                                 │   User Natural Prompt        │
                                 │  "Generate Helldivers 2      │
                                 │   stratagem macro pack"      │
                                 └──────────────┬───────────────┘
                                                │
                                                ▼
                                 ┌──────────────────────────────┐
                                 │   Strop AI Assistant Client  │
                                 │  • Gemini API / OpenAI API   │
                                 │  • Local Ollama (Offline)    │
                                 │  • System Prompt with syntax │
                                 └──────────────┬───────────────┘
                                                │ Validated JSON
                                                ▼
                                 ┌──────────────────────────────┐
                                 │   Strop Macro Library Store  │
                                 │   ~/.config/strop/macros/    │
                                 │   ├── helldivers_2.json      │
                                 │   ├── fighting_combos.json   │
                                 │   └── productivity.json      │
                                 └──────────────┬───────────────┘
                                                │
                     ┌──────────────────────────┴──────────────────────────┐
                     ▼                                                     ▼
        ┌─────────────────────────┐                           ┌─────────────────────────┐
        │   Studio Macro Drawer   │                           │     In-Game HUD         │
        │   (Click to bind key)   │                           │   (Quick Macro Palette) │
        └─────────────────────────┘                           └─────────────────────────┘
```

---

## 📦 Core Pillars

### 1. Multi-Provider AI Assistant Engine
- **Supported Providers**:
  - **Google Gemini** (`gemini-2.0-flash` / `gemini-1.5-pro` via API key).
  - **OpenAI ChatGPT** (`gpt-4o` / `gpt-4o-mini` via API key).
  - **Local Ollama** (e.g. `llama3`, `mistral`, `deepseek-r1` running on `http://localhost:11434` for 100% offline privacy).
- **Domain System Prompt**:
  - Encodes the exact macro syntax specifications (`w . 50ms . s`, `hold(w, d)`, `mouse(1)`, `key_down(ctrl) . c . key_up(ctrl)`).
  - Enforces structured JSON responses with validated input codes and metadata.

---

### 2. Standardized Macro Catalog Schema (`~/.config/strop/macros/*.json`)
```json
{
  "category": "Helldivers 2",
  "game_id": "helldivers_2",
  "author": "AI Generated (Gemini)",
  "version": "1.0",
  "macros": [
    {
      "id": "reinforce",
      "name": "Reinforce",
      "custom_name": "Respawn",
      "description": "Call down reinforcement hellpod",
      "target_uinput": "keyboard",
      "macro": "w . 50ms . s . 50ms . d . 50ms . a . 50ms . w",
      "tags": ["survival", "support"]
    },
    {
      "id": "500kg_bomb",
      "name": "Eagle 500kg Bomb",
      "custom_name": "500kg",
      "description": "Heavy high-yield ordnance air strike",
      "target_uinput": "keyboard",
      "macro": "w . 50ms . d . 50ms . s . 50ms . s . 50ms . s",
      "tags": ["eagle", "offensive"]
    },
    {
      "id": "autocannon",
      "name": "AC-8 Autocannon",
      "custom_name": "AutoCannon",
      "description": "Call down heavy support weapon & backpack",
      "target_uinput": "keyboard",
      "macro": "s . 50ms . a . 50ms . s . 50ms . w . 50ms . w . 50ms . d",
      "tags": ["support_weapon"]
    }
  ]
}
```

---

### 3. Studio GUI Integration
- **`📚 Macro Library` Tab**: Added to the Special Actions dock next to `⚡ Actions` and `🕹 Emulation`.
- **Search & Game Category Selector**: Filter by game (e.g. *Helldivers 2*, *Street Fighter 6*, *World of Warcraft*, *Blender*).
- **1-Click Key Assignment**: Selecting any key on the canvas and clicking a macro card instantly binds both the **Output Macro** and the **Custom Action Name** (e.g. `500kg`).

---

### 4. Interactive AI Generator Modal
- **Prompt Input Box**: *"Generate all 4-directional defensive stratagems for Helldivers 2 with 40ms delays"*.
- **Live Preview & Test**: Preview generated macros, test in a sandbox input listener, and click **"Save to Library"**.
