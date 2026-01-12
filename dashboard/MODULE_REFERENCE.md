# Dashboard Module Reference

Quick reference guide for the modularized dashboard codebase.

## Module Files

### 1. `scene.js` (124 lines)
**Purpose**: Three.js scene initialization and management

**Exports**:
- `scene` - THREE.Scene instance
- `camera` - THREE.PerspectiveCamera
- `renderer` - THREE.WebGLRenderer
- `controls` - OrbitControls
- `starField` - Background stars
- `raycaster` - For object picking
- `mouse` - Mouse position vector
- `DEFAULT_CAMERA_POS` - Default camera position
- `DEFAULT_TARGET` - Default camera target
- `initScene()` - Initialize everything
- `updateControls()` - Update controls (call in animation loop)
- `renderScene()` - Render the scene

**Usage**:
```javascript
import { initScene, updateControls, renderScene } from './scene.js';
```

---

### 2. `api.js` (590 lines)
**Purpose**: All backend API communication

**Key Exports** (40+ functions):

#### Portfolio Data
- `fetchPortfolioData()` - Get current portfolio state
- `fetchEvents(limit)` - Get event history
- `fetchEventSnapshot(eventId)` - Get portfolio state at event
- `fetchPlaybackTimeline()` - Get prepared timeline data

#### Price Management
- `fetchPriceQuote(ticker)` - Get quote for single ticker
- `updatePrices()` - Refresh all prices

#### Alternate Histories
- `fetchAlternateHistories()` - List all alternate histories
- `fetchAlternateHistory(id)` - Get single history
- `compareHistories(id1, id2)` - Compare two histories
- `createAlternateHistory(data)` - Create new history
- `deleteAlternateHistory(id)` - Delete history

#### Projections
- `generateProjection(data)` - Generate future projection
- `fetchProjections()` - List saved projections
- `fetchProjection(id)` - Get single projection
- `deleteProjection(id)` - Delete projection

#### Ideas/Brainstorming
- `fetchIdeas()` - Get all ideas
- `fetchIdeasAsMods()` - Get ideas as modifications
- `createIdea(data)` - Create new idea
- `manifestIdea(id)` - Convert idea to alternate history
- `archiveIdea(id)` - Archive idea
- `toggleIdeaActive(id)` - Toggle idea on/off

#### LLM/AI
- `fetchLLMConfig()` - Get LLM configuration
- `saveLLMConfig(config)` - Update LLM config
- `checkLLMStatus()` - Check LLM availability
- `testLLMConnection()` - Test LLM connection
- `fetchDexterStatus()` - Get Dexter/MCP status
- `fetchResearchInsights()` - Get AI insights

#### Chat
- `sendChatMessage(message, streaming)` - Send chat message
- `fetchChatUsage()` - Get token usage
- `fetchChatSession()` - Get session stats

#### Setup
- `checkSetupStatus()` - Check if setup needed
- `checkDemoMode()` - Check if in demo mode
- `initDemo()` - Initialize demo data
- `initFresh(data)` - Initialize fresh portfolio
- `uploadCSV(formData)` - Upload event log CSV
- `exitDemo()` - Exit demo mode

#### Scanner
- `fetchScannerRecommendations()` - Get options recommendations
- `fetchAnalyzedRecommendations()` - Get analyzed recommendations
- `fetchAgentRecommendations()` - Get agent-generated recommendations

**Usage**:
```javascript
import { fetchPortfolioData, updatePrices } from './api.js';
```

---

### 3. `planets.js` (515 lines)
**Purpose**: Planet creation and visualization

**Exports**:
- `planets` - Map of ticker -> {group, orbit}
- `sun` - Sun mesh
- `createSun()` - Create central sun
- `createPlanet(holding, index, total, portfolioTotal)` - Create planet for holding
- `updatePlanets(deltaTime)` - Animate all planets
- `clearPlanets()` - Remove all planets from scene
- `createPlanetTexture(baseColor, isGain)` - Generate procedural texture
- `createAtmosphere(radius, isGain, intensity)` - Create glow
- `createMomentumParticles(radius, momentum)` - Create particle ring
- `createDayChangeIndicator(radius, dayChangePct)` - Create day change arrow
- `createPartialRing(...)` - Helper for ring geometry

**Planet Data Structure**:
```javascript
{
  type: 'planet',
  ticker: 'TSLA',
  shares: 100,
  market_value: 44500,
  gain_pct: 15.2,
  day_change_pct: 2.3,
  allocation_pct: 25.5,
  orbitRadius: 18.5,
  orbitSpeed: 0.0005,
  orbitAngle: 1.57,
  rotationSpeed: 0.003,
  momentum: 0.152,
  particles: Points,
  planet: Mesh,
  dayChangeIndicator: Group
}
```

**Usage**:
```javascript
import { createSun, createPlanet, updatePlanets } from './planets.js';

createSun();
holdings.forEach((holding, i) => {
  createPlanet(holding, i, holdings.length, totalValue);
});

// In animation loop:
updatePlanets(deltaTime);
```

---

### 4. `main.js` (453 lines)
**Purpose**: Application entry point and orchestration

**Key Functions**:
- `init()` - Initialize Three.js scene
- `animate()` - Main animation loop
- `main()` - Application entry point
- `updateHUD(data)` - Update HUD display
- `focusOnPlanet(ticker)` - Zoom to planet
- `zoomToSystem()` - Zoom out to full view
- `animateCameraTo(pos, target)` - Smooth camera movement
- `onCanvasClick(event)` - Handle planet clicks
- `onCanvasMouseMove(event)` - Handle hover
- `refreshPrices()` - Update all prices
- `checkAIStatus()` - Check AI/MCP availability
- `exitDemoMode()` - Exit demo

**Global Window Functions** (for HTML onclick):
- `window.focusOnPlanet(ticker)`
- `window.zoomToSystem()`
- `window.navigateTo(path)`
- `window.refreshPrices()`
- `window.exitDemoMode()`

**Usage**:
```javascript
// Called automatically on page load
// No manual invocation needed
```

---

## Data Flow

```
HTML (index.html)
  ↓
main.js (entry point)
  ├─→ scene.js (initialize Three.js)
  ├─→ api.js (fetch data)
  └─→ planets.js (create visualization)

Animation Loop:
  animate() in main.js
    ├─→ updateControls() from scene.js
    ├─→ updatePlanets(deltaTime) from planets.js
    └─→ renderScene() from scene.js
```

## Common Tasks

### Add New API Endpoint
1. Add function to `api.js`
2. Export it
3. Import in `main.js` or other modules
4. Use it

### Add New Visual Effect
1. Add function to `planets.js`
2. Call from `createPlanet()` or `updatePlanets()`
3. Store effect reference in `planetGroup.userData`

### Add New UI Interaction
1. Add event listener in `main.js` `init()`
2. Create handler function
3. Access planets via `planets.get(ticker)`
4. Update camera via `animateCameraTo()`

### Debug Issues
1. Check browser console for errors
2. Verify imports/exports match
3. Check that all functions are exported
4. Ensure proper file paths in imports

## Build Commands

```bash
# Development server (auto-reload)
cd dashboard
npm run dev

# Production build
cd dashboard
npm run build

# Preview production build
cd dashboard
npm run preview
```

## File Sizes

| File | Lines | Size |
|------|-------|------|
| `scene.js` | 124 | 3.3 KB |
| `api.js` | 590 | 16 KB |
| `planets.js` | 515 | 17 KB |
| `main.js` | 453 | 14 KB |
| **Total** | **1,682** | **~50 KB** |

Compare to original: **7,941 lines, 302 KB**

---

## Future Modularization

Still in `main_original.js`:

1. **`tracker.js`** (~500 lines)
   - Tracked tickers feature
   - Planet destruction animations

2. **`realities.js`** (~3000 lines)
   - Alternate reality visualization
   - Cluster view
   - Timeline components

3. **`ui.js`** (~2000 lines)
   - Modal dialogs
   - Settings panels
   - Chat interface

4. **`effects.js`** (~500 lines)
   - Cataclysm effect
   - Cash planet
   - Special animations

---

*Last updated: 2026-01-12*
