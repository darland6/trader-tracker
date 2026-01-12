/**
 * Portfolio Multiverse - Alternate Realities Visualization
 * Three.js multi-solar-system view with cosmic event animations
 *
 * Features:
 * - Planet birth animation for BUY events (particles coalesce into planet)
 * - Asteroid collision for SELL events (piece breaks off)
 * - Smooth timeline playback with play/pause
 * - LLM-powered projections and macro events
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// State
let scene, camera, renderer, controls;
let realities = [];
let selectedReality = null;
let timelinePosition = 0.5; // 0 = past, 0.5 = present, 1 = future
let animationTime = 0;
let projectionData = null;
let macroEvents = [];
let currentMacroEventIndex = -1;

// Timeline playback state
let isPlaying = false;
let playbackSpeed = 1; // 1 = normal, 2 = fast, 0.5 = slow
let playbackFrameIndex = 0;
let lastPlaybackTime = 0;
let playbackData = {}; // { reality_id: { frames, events } }

// Active animations
let activeAnimations = [];
let particleSystems = [];

// Timeline bounds
let timelineStart = null;
let timelineEnd = null;
let timelinePresent = null;

// Colors for different realities
const REALITY_COLORS = {
    main: 0x06b6d4,      // Cyan for main reality
    alt1: 0x9333ea,      // Purple
    alt2: 0xf59e0b,      // Amber
    alt3: 0xef4444,      // Red
    alt4: 0x22c55e,      // Green
    alt5: 0xec4899       // Pink
};

// Ticker colors for planets
const TICKER_COLORS = {
    TSLA: 0xc0c0c0,  // Silver
    META: 0x1877f2,  // Facebook blue
    NVDA: 0x76b900,  // NVIDIA green
    PLTR: 0x000000,  // Black
    RKLB: 0xff6b00,  // Rocket orange
    BMNR: 0xffd700,  // Gold
    NBIS: 0x00d4aa,  // Teal
    AMD: 0xed1c24,   // AMD red
    MSFT: 0x00a4ef,  // Microsoft blue
    GOOGL: 0x4285f4, // Google blue
    AAPL: 0xa2aaad,  // Apple gray
    SPY: 0x1a1a2e,   // Dark blue
    QQQ: 0x4a00e0    // Purple
};

// Initialize
async function init() {
    setupScene();
    setupLighting();
    setupControls();
    await loadRealities();
    await loadPlaybackData();
    createMultiverse();
    hideLoading();
    animate();
    setupEventListeners();
    setupCreateModal();
    setupPlaybackControls();
}

function setupScene() {
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x050510);

    // Camera
    camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 10000);
    camera.position.set(0, 300, 500);
    camera.lookAt(0, 0, 0);

    // Renderer
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    document.getElementById('canvas-container').appendChild(renderer.domElement);

    // Add starfield
    createStarfield();

    // Add ambient nebula
    createNebula();
}

function createStarfield() {
    const starGeometry = new THREE.BufferGeometry();
    const starCount = 5000;
    const positions = new Float32Array(starCount * 3);
    const colors = new Float32Array(starCount * 3);

    for (let i = 0; i < starCount; i++) {
        const i3 = i * 3;
        const radius = 2000 + Math.random() * 3000;
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(2 * Math.random() - 1);

        positions[i3] = radius * Math.sin(phi) * Math.cos(theta);
        positions[i3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
        positions[i3 + 2] = radius * Math.cos(phi);

        // Slight color variation
        const intensity = 0.5 + Math.random() * 0.5;
        colors[i3] = intensity;
        colors[i3 + 1] = intensity;
        colors[i3 + 2] = intensity;
    }

    starGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    starGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const starMaterial = new THREE.PointsMaterial({
        size: 2,
        vertexColors: true,
        transparent: true,
        opacity: 0.8
    });

    const stars = new THREE.Points(starGeometry, starMaterial);
    scene.add(stars);
}

function createNebula() {
    // Create subtle nebula clouds using sprites
    const nebulaTexture = createNebulaTexture();

    for (let i = 0; i < 20; i++) {
        const spriteMaterial = new THREE.SpriteMaterial({
            map: nebulaTexture,
            color: i % 2 === 0 ? 0x9333ea : 0x06b6d4,
            transparent: true,
            opacity: 0.03,
            blending: THREE.AdditiveBlending
        });

        const sprite = new THREE.Sprite(spriteMaterial);
        sprite.position.set(
            (Math.random() - 0.5) * 2000,
            (Math.random() - 0.5) * 1000,
            (Math.random() - 0.5) * 2000
        );
        sprite.scale.set(800, 800, 1);
        scene.add(sprite);
    }
}

function createNebulaTexture() {
    const canvas = document.createElement('canvas');
    canvas.width = 256;
    canvas.height = 256;
    const ctx = canvas.getContext('2d');

    const gradient = ctx.createRadialGradient(128, 128, 0, 128, 128, 128);
    gradient.addColorStop(0, 'rgba(255, 255, 255, 1)');
    gradient.addColorStop(0.3, 'rgba(255, 255, 255, 0.5)');
    gradient.addColorStop(1, 'rgba(255, 255, 255, 0)');

    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, 256, 256);

    return new THREE.CanvasTexture(canvas);
}

function setupLighting() {
    const ambientLight = new THREE.AmbientLight(0x404040, 0.5);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(100, 200, 100);
    scene.add(directionalLight);
}

function setupControls() {
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.minDistance = 100;
    controls.maxDistance = 2000;
    controls.maxPolarAngle = Math.PI * 0.85;
}

async function loadRealities() {
    try {
        // Fetch alternate histories from API
        const response = await fetch('/api/alt-history');
        if (response.ok) {
            const data = await response.json();
            realities = data.histories || [];
        }
    } catch (e) {
        console.log('No alternate histories API, using demo data');
    }

    // Add main reality
    const stateResponse = await fetch('/api/state');
    const mainState = await stateResponse.json();

    realities.unshift({
        id: 'reality',
        name: 'Current Reality',
        description: 'Your actual portfolio',
        isMain: true,
        state: mainState
    });

    // If no alternate histories, create demo ones
    if (realities.length < 2) {
        realities.push(
            createDemoReality('bull', 'Bull Scenario', 'If all positions gained 20%', mainState, 1.2),
            createDemoReality('bear', 'Bear Scenario', 'If all positions dropped 20%', mainState, 0.8),
            createDemoReality('diamond', 'Diamond Hands', 'Never sold any positions', mainState, 1.35)
        );
    }
}

async function loadPlaybackData() {
    // Show loading status
    showLoadingStatus('Loading historical data...');

    // Load playback data for each reality in parallel
    const playbackPromises = realities.map(async (reality) => {
        try {
            const response = await fetch(`/api/alt-history/${reality.id}/playback?use_interpolation=true`);
            if (response.ok) {
                const data = await response.json();
                playbackData[reality.id] = data;

                // Extract events for this reality
                reality.events = data.events || [];
                reality.frames = data.frames || [];

                console.log(`Loaded ${reality.events.length} events, ${reality.frames.length} frames for ${reality.name}`);
            }
        } catch (e) {
            console.log(`Could not load playback data for ${reality.id}:`, e);
        }
    });

    await Promise.all(playbackPromises);

    // Set timeline bounds from data
    if (realities[0]?.frames?.length > 0) {
        const frames = realities[0].frames;
        timelineStart = new Date(frames[0].date);
        timelineEnd = new Date(frames[frames.length - 1].date);
        timelinePresent = new Date();
    }

    // Now load LLM projections for future timeline
    await loadLLMProjections();
}

async function loadLLMProjections() {
    showLoadingStatus('Generating LLM projections...');

    // Load projections for each reality using LLM
    for (const reality of realities) {
        try {
            // Request LLM-powered projection
            const response = await fetch(`/api/alt-history/${reality.id}/project?years=3&use_llm=true`);

            if (response.ok) {
                const projection = await response.json();
                reality.projection = projection;

                // Merge projection frames with historical frames
                if (projection.frames) {
                    // Find the last historical date
                    const lastHistoricalDate = reality.frames?.[reality.frames.length - 1]?.date;

                    // Add projection frames after historical data
                    const projectionFrames = projection.frames
                        .filter(f => !lastHistoricalDate || f.date > lastHistoricalDate)
                        .map(f => ({
                            ...f,
                            isProjection: true,
                            confidence: projection.confidence || 'medium'
                        }));

                    reality.frames = [...(reality.frames || []), ...projectionFrames];
                }

                // Store LLM analysis
                if (projection.llm_analysis) {
                    reality.llmAnalysis = projection.llm_analysis;
                }

                console.log(`LLM projection loaded for ${reality.name}:`, {
                    projectionFrames: projection.frames?.length || 0,
                    hasLLMAnalysis: !!projection.llm_analysis
                });
            }
        } catch (e) {
            console.log(`Could not load LLM projection for ${reality.id}:`, e);
        }
    }

    // Update timeline bounds to include projections
    updateTimelineBounds();

    // Load macro events from LLM
    await loadMacroEvents();
}

async function loadMacroEvents() {
    showLoadingStatus('Identifying macro events...');

    try {
        // Ask LLM to identify significant macro events in the timeline
        const response = await fetch('/api/chat/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: `Analyze the portfolio timeline and identify 5-7 significant macro events that affected or could affect the portfolio. For each event provide:
                - date (YYYY-MM-DD)
                - title (short headline)
                - description (1-2 sentences)
                - impact: "positive" or "negative"

                Consider market events, economic news, and portfolio-specific milestones.
                Return as JSON array.`,
                context: 'macro_events'
            })
        });

        if (response.ok) {
            const data = await response.json();

            // Try to parse macro events from LLM response
            try {
                const eventsMatch = data.response?.match(/\[[\s\S]*\]/);
                if (eventsMatch) {
                    macroEvents = JSON.parse(eventsMatch[0]);
                    console.log('Loaded macro events from LLM:', macroEvents.length);
                }
            } catch (e) {
                console.log('Could not parse macro events, using defaults');
                macroEvents = getDefaultMacroEvents();
            }
        }
    } catch (e) {
        console.log('Could not load macro events:', e);
        macroEvents = getDefaultMacroEvents();
    }
}

function getDefaultMacroEvents() {
    return [
        {
            date: '2024-03-01',
            title: 'AI Boom Acceleration',
            description: 'NVIDIA earnings beat expectations, driving tech sector rally',
            impact: 'positive'
        },
        {
            date: '2024-07-15',
            title: 'Fed Rate Decision',
            description: 'Federal Reserve signals potential rate cuts',
            impact: 'positive'
        },
        {
            date: '2025-01-01',
            title: 'New Year Rebalancing',
            description: 'Annual portfolio rebalancing and tax-loss harvesting',
            impact: 'neutral'
        }
    ];
}

function updateTimelineBounds() {
    // Find earliest and latest dates across all realities
    let earliest = null;
    let latest = null;

    for (const reality of realities) {
        if (reality.frames?.length > 0) {
            const first = new Date(reality.frames[0].date);
            const last = new Date(reality.frames[reality.frames.length - 1].date);

            if (!earliest || first < earliest) earliest = first;
            if (!latest || last > latest) latest = last;
        }
    }

    if (earliest) timelineStart = earliest;
    if (latest) timelineEnd = latest;
    timelinePresent = new Date();

    console.log('Timeline bounds updated:', {
        start: timelineStart?.toISOString().split('T')[0],
        end: timelineEnd?.toISOString().split('T')[0],
        present: timelinePresent.toISOString().split('T')[0]
    });
}

function showLoadingStatus(message) {
    const loading = document.getElementById('loading');
    if (loading) {
        const textEl = loading.querySelector('.loading-text');
        if (textEl) {
            textEl.textContent = message;
        }
    }
}

function createDemoReality(id, name, description, baseState, multiplier) {
    const altState = JSON.parse(JSON.stringify(baseState));

    // Modify values
    altState.total_value = (altState.total_value || 0) * multiplier;
    altState.portfolio_value = (altState.portfolio_value || 0) * multiplier;

    if (altState.holdings) {
        for (const holding of altState.holdings) {
            holding.market_value *= multiplier;
            holding.unrealized_gain = holding.market_value - holding.cost_basis;
        }
    }

    return {
        id,
        name,
        description,
        isMain: false,
        state: altState,
        divergence_point: '2025-06-01',
        gain_vs_reality: ((multiplier - 1) * 100).toFixed(1),
        events: [],
        frames: []
    };
}

function createMultiverse() {
    const spacing = 300;
    const cols = Math.ceil(Math.sqrt(realities.length));

    realities.forEach((reality, index) => {
        const row = Math.floor(index / cols);
        const col = index % cols;

        const x = (col - (cols - 1) / 2) * spacing;
        const z = (row - Math.floor(realities.length / cols) / 2) * spacing;

        const solarSystem = createSolarSystem(reality, index);
        solarSystem.position.set(x, 0, z);
        solarSystem.userData.reality = reality;
        solarSystem.userData.index = index;
        scene.add(solarSystem);

        reality.solarSystem = solarSystem;
        reality.basePosition = new THREE.Vector3(x, 0, z);
        reality.planets = {}; // Track planets by ticker
    });

    // Create reality cards in UI
    updateRealityPanel();

    // Create connection lines between realities
    createConnections();
}

function createSolarSystem(reality, index) {
    const group = new THREE.Group();
    const state = reality.state || {};
    const totalValue = state.total_value || state.portfolio_value || 500000;
    const isMain = reality.isMain;

    // Sun size based on total value (scaled)
    const sunRadius = Math.max(15, Math.min(40, Math.sqrt(totalValue / 10000)));
    const color = isMain ? REALITY_COLORS.main : Object.values(REALITY_COLORS)[index % 6];

    // Create sun (core)
    const sunGeometry = new THREE.SphereGeometry(sunRadius, 32, 32);
    const sunMaterial = new THREE.MeshBasicMaterial({
        color: color,
        transparent: true,
        opacity: 0.9
    });
    const sun = new THREE.Mesh(sunGeometry, sunMaterial);
    sun.userData.type = 'sun';
    sun.userData.reality = reality;
    group.add(sun);

    // Sun glow
    const glowGeometry = new THREE.SphereGeometry(sunRadius * 1.5, 32, 32);
    const glowMaterial = new THREE.MeshBasicMaterial({
        color: color,
        transparent: true,
        opacity: 0.2,
        side: THREE.BackSide
    });
    const glow = new THREE.Mesh(glowGeometry, glowMaterial);
    group.add(glow);

    // Outer glow sprite
    const glowSprite = createGlowSprite(color, sunRadius * 4);
    group.add(glowSprite);

    // Create planets for holdings
    const holdings = state.holdings || [];
    const sortedHoldings = [...holdings].sort((a, b) => (b.market_value || 0) - (a.market_value || 0));

    sortedHoldings.slice(0, 8).forEach((holding, i) => {
        const planet = createPlanet(holding, i, sunRadius, color);
        group.add(planet);

        // Track planet by ticker
        reality.planets = reality.planets || {};
        reality.planets[holding.ticker] = planet;
    });

    // Label
    const label = createLabel(reality.name, sunRadius);
    label.position.y = -sunRadius - 20;
    group.add(label);

    // Value label
    const valueLabel = createValueLabel(totalValue, sunRadius);
    valueLabel.position.y = sunRadius + 15;
    valueLabel.userData.valueLabel = true;
    group.add(valueLabel);

    return group;
}

function createPlanet(holding, index, sunRadius, systemColor) {
    const group = new THREE.Group();
    const value = holding.market_value || 0;
    const planetRadius = Math.max(3, Math.min(15, Math.sqrt(value / 3000)));
    const orbitRadius = sunRadius * 2 + (index + 1) * 18;

    // Planet color - use ticker color if available
    const ticker = holding.ticker || '';
    let planetColor = TICKER_COLORS[ticker] || systemColor;

    // Tint based on gain/loss
    const gain = holding.unrealized_gain || 0;
    if (gain > 0) {
        planetColor = new THREE.Color(planetColor).lerp(new THREE.Color(0x00ff88), 0.3).getHex();
    } else if (gain < 0) {
        planetColor = new THREE.Color(planetColor).lerp(new THREE.Color(0xff4444), 0.3).getHex();
    }

    // Planet mesh
    const geometry = new THREE.SphereGeometry(planetRadius, 24, 24);
    const material = new THREE.MeshStandardMaterial({
        color: planetColor,
        metalness: 0.4,
        roughness: 0.6,
        emissive: planetColor,
        emissiveIntensity: 0.15
    });
    const planet = new THREE.Mesh(geometry, material);

    // Initial position on orbit
    const angle = (index / 8) * Math.PI * 2 + Math.random() * 0.5;
    planet.position.x = Math.cos(angle) * orbitRadius;
    planet.position.z = Math.sin(angle) * orbitRadius;

    planet.userData.holding = holding;
    planet.userData.ticker = ticker;
    planet.userData.orbitRadius = orbitRadius;
    planet.userData.orbitSpeed = 0.15 / (index + 1);
    planet.userData.orbitAngle = angle;
    planet.userData.baseRadius = planetRadius;

    group.add(planet);

    // Orbit ring
    const orbitGeometry = new THREE.RingGeometry(orbitRadius - 0.5, orbitRadius + 0.5, 64);
    const orbitMaterial = new THREE.MeshBasicMaterial({
        color: systemColor,
        transparent: true,
        opacity: 0.08,
        side: THREE.DoubleSide
    });
    const orbit = new THREE.Mesh(orbitGeometry, orbitMaterial);
    orbit.rotation.x = Math.PI / 2;
    group.add(orbit);

    // Planet label
    const planetLabel = createPlanetLabel(ticker, planetRadius);
    planetLabel.position.y = planetRadius + 5;
    planet.add(planetLabel);

    return group;
}

function createPlanetLabel(text, planetRadius) {
    const canvas = document.createElement('canvas');
    canvas.width = 128;
    canvas.height = 32;
    const ctx = canvas.getContext('2d');

    ctx.font = 'bold 18px Arial';
    ctx.textAlign = 'center';
    ctx.fillStyle = '#ffffff';
    ctx.fillText(text, 64, 22);

    const texture = new THREE.CanvasTexture(canvas);
    const material = new THREE.SpriteMaterial({
        map: texture,
        transparent: true
    });

    const sprite = new THREE.Sprite(material);
    sprite.scale.set(20, 5, 1);
    return sprite;
}

function createGlowSprite(color, size) {
    const canvas = document.createElement('canvas');
    canvas.width = 128;
    canvas.height = 128;
    const ctx = canvas.getContext('2d');

    const gradient = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);

    const c = new THREE.Color(color);
    gradient.addColorStop(0, `rgba(${Math.floor(c.r * 255)}, ${Math.floor(c.g * 255)}, ${Math.floor(c.b * 255)}, 0.5)`);
    gradient.addColorStop(0.5, `rgba(${Math.floor(c.r * 255)}, ${Math.floor(c.g * 255)}, ${Math.floor(c.b * 255)}, 0.1)`);
    gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');

    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, 128, 128);

    const texture = new THREE.CanvasTexture(canvas);
    const material = new THREE.SpriteMaterial({
        map: texture,
        transparent: true,
        blending: THREE.AdditiveBlending
    });

    const sprite = new THREE.Sprite(material);
    sprite.scale.set(size, size, 1);
    return sprite;
}

function createLabel(text, sunRadius) {
    const canvas = document.createElement('canvas');
    canvas.width = 256;
    canvas.height = 64;
    const ctx = canvas.getContext('2d');

    ctx.font = 'bold 24px Arial';
    ctx.textAlign = 'center';
    ctx.fillStyle = '#ffffff';
    ctx.fillText(text, 128, 40);

    const texture = new THREE.CanvasTexture(canvas);
    const material = new THREE.SpriteMaterial({
        map: texture,
        transparent: true
    });

    const sprite = new THREE.Sprite(material);
    sprite.scale.set(80, 20, 1);
    return sprite;
}

function createValueLabel(value, sunRadius) {
    const canvas = document.createElement('canvas');
    canvas.width = 256;
    canvas.height = 64;
    const ctx = canvas.getContext('2d');

    ctx.font = 'bold 20px monospace';
    ctx.textAlign = 'center';
    ctx.fillStyle = '#00ff88';
    ctx.fillText(`$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, 128, 40);

    const texture = new THREE.CanvasTexture(canvas);
    const material = new THREE.SpriteMaterial({
        map: texture,
        transparent: true
    });

    const sprite = new THREE.Sprite(material);
    sprite.scale.set(80, 20, 1);
    return sprite;
}

// ==================== COSMIC ANIMATIONS ====================

/**
 * Planet Birth Animation - for BUY events
 * Particles coalesce from space into a forming planet
 */
function createPlanetBirthAnimation(reality, ticker, shares, price, position) {
    const system = reality.solarSystem;
    if (!system) return;

    const value = shares * price;
    const planetRadius = Math.max(3, Math.min(15, Math.sqrt(value / 3000)));
    const color = TICKER_COLORS[ticker] || 0x00ff88;

    // Create particle system for birth effect
    const particleCount = 200;
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    const velocities = [];
    const targetPos = position || new THREE.Vector3(
        (Math.random() - 0.5) * 100,
        0,
        (Math.random() - 0.5) * 100
    );

    // Initialize particles scattered in space
    for (let i = 0; i < particleCount; i++) {
        const i3 = i * 3;
        const angle = Math.random() * Math.PI * 2;
        const dist = 50 + Math.random() * 100;

        positions[i3] = targetPos.x + Math.cos(angle) * dist;
        positions[i3 + 1] = targetPos.y + (Math.random() - 0.5) * 50;
        positions[i3 + 2] = targetPos.z + Math.sin(angle) * dist;

        // Velocity toward center
        velocities.push({
            x: (targetPos.x - positions[i3]) * 0.02,
            y: (targetPos.y - positions[i3 + 1]) * 0.02,
            z: (targetPos.z - positions[i3 + 2]) * 0.02
        });
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

    const material = new THREE.PointsMaterial({
        color: color,
        size: 3,
        transparent: true,
        opacity: 0.8,
        blending: THREE.AdditiveBlending
    });

    const particles = new THREE.Points(geometry, material);
    system.add(particles);

    // Animation state
    const animation = {
        type: 'birth',
        particles,
        velocities,
        targetPos,
        ticker,
        planetRadius,
        color,
        progress: 0,
        duration: 2.5, // seconds
        reality,
        onComplete: () => {
            // Remove particles
            system.remove(particles);
            geometry.dispose();
            material.dispose();

            // Create the actual planet
            const orbitIndex = Object.keys(reality.planets || {}).length;
            const sunRadius = 25;
            const holding = {
                ticker,
                shares,
                market_value: value,
                unrealized_gain: 0
            };

            const planet = createPlanet(holding, orbitIndex, sunRadius, REALITY_COLORS.main);
            system.add(planet);
            reality.planets[ticker] = planet;

            // Flash effect
            createFlashEffect(system, targetPos, color);
        }
    };

    activeAnimations.push(animation);

    // Show event notification
    showEventNotification(`Buying ${shares} shares of ${ticker}`, 'buy');
}

/**
 * Asteroid Collision Animation - for SELL events
 * Piece breaks off from planet with debris
 */
function createAsteroidCollisionAnimation(reality, ticker, shares, price) {
    const system = reality.solarSystem;
    const planet = reality.planets?.[ticker];

    if (!system || !planet) return;

    // Find the planet mesh
    let planetMesh = null;
    planet.traverse(obj => {
        if (obj.userData.ticker === ticker) {
            planetMesh = obj;
        }
    });

    if (!planetMesh) return;

    const planetPos = new THREE.Vector3();
    planetMesh.getWorldPosition(planetPos);
    system.worldToLocal(planetPos);

    // Create asteroid
    const asteroidGeometry = new THREE.DodecahedronGeometry(3, 0);
    const asteroidMaterial = new THREE.MeshStandardMaterial({
        color: 0x888888,
        roughness: 0.9,
        metalness: 0.1
    });
    const asteroid = new THREE.Mesh(asteroidGeometry, asteroidMaterial);

    // Start asteroid from afar
    const asteroidStart = new THREE.Vector3(
        planetPos.x + 150,
        planetPos.y + 50,
        planetPos.z + 100
    );
    asteroid.position.copy(asteroidStart);
    system.add(asteroid);

    // Create debris particles
    const debrisCount = 100;
    const debrisGeometry = new THREE.BufferGeometry();
    const debrisPositions = new Float32Array(debrisCount * 3);
    const debrisVelocities = [];

    for (let i = 0; i < debrisCount; i++) {
        const i3 = i * 3;
        debrisPositions[i3] = planetPos.x;
        debrisPositions[i3 + 1] = planetPos.y;
        debrisPositions[i3 + 2] = planetPos.z;
        debrisVelocities.push({
            x: (Math.random() - 0.5) * 5,
            y: (Math.random() - 0.5) * 5,
            z: (Math.random() - 0.5) * 5
        });
    }

    debrisGeometry.setAttribute('position', new THREE.BufferAttribute(debrisPositions, 3));

    const debrisMaterial = new THREE.PointsMaterial({
        color: TICKER_COLORS[ticker] || 0xff6600,
        size: 2,
        transparent: true,
        opacity: 0,
        blending: THREE.AdditiveBlending
    });

    const debris = new THREE.Points(debrisGeometry, debrisMaterial);
    system.add(debris);

    // Animation state
    const animation = {
        type: 'collision',
        asteroid,
        debris,
        debrisVelocities,
        planetMesh,
        planetPos,
        asteroidStart,
        ticker,
        shares,
        progress: 0,
        phase: 'approach', // approach, impact, explosion
        duration: 3,
        reality,
        onComplete: () => {
            // Cleanup
            system.remove(asteroid);
            system.remove(debris);
            asteroidGeometry.dispose();
            asteroidMaterial.dispose();
            debrisGeometry.dispose();
            debrisMaterial.dispose();

            // Shrink the planet
            const currentRadius = planetMesh.userData.baseRadius || 10;
            const holding = planetMesh.userData.holding;
            if (holding) {
                const newValue = Math.max(0, holding.market_value - (shares * price));
                const newRadius = Math.max(2, Math.sqrt(newValue / 3000));

                // Animate shrink
                animatePlanetShrink(planetMesh, newRadius / currentRadius);

                // Update holding
                holding.market_value = newValue;
                holding.shares = Math.max(0, holding.shares - shares);
            }
        }
    };

    activeAnimations.push(animation);

    // Show event notification
    showEventNotification(`Selling ${shares} shares of ${ticker}`, 'sell');
}

/**
 * Flash effect at position
 */
function createFlashEffect(parent, position, color) {
    const flashGeometry = new THREE.SphereGeometry(5, 16, 16);
    const flashMaterial = new THREE.MeshBasicMaterial({
        color: color,
        transparent: true,
        opacity: 1,
        blending: THREE.AdditiveBlending
    });
    const flash = new THREE.Mesh(flashGeometry, flashMaterial);
    flash.position.copy(position);
    parent.add(flash);

    // Animate flash
    const startTime = Date.now();
    const animate = () => {
        const elapsed = (Date.now() - startTime) / 1000;
        if (elapsed < 0.5) {
            flash.scale.setScalar(1 + elapsed * 10);
            flashMaterial.opacity = 1 - elapsed * 2;
            requestAnimationFrame(animate);
        } else {
            parent.remove(flash);
            flashGeometry.dispose();
            flashMaterial.dispose();
        }
    };
    animate();
}

/**
 * Animate planet shrinking
 */
function animatePlanetShrink(planetMesh, scaleFactor) {
    const startScale = planetMesh.scale.x;
    const endScale = startScale * scaleFactor;
    const startTime = Date.now();
    const duration = 500;

    const animate = () => {
        const elapsed = Date.now() - startTime;
        const t = Math.min(1, elapsed / duration);
        const eased = 1 - Math.pow(1 - t, 3);

        const scale = startScale + (endScale - startScale) * eased;
        planetMesh.scale.setScalar(scale);

        if (t < 1) {
            requestAnimationFrame(animate);
        }
    };
    animate();
}

/**
 * Show event notification
 */
function showEventNotification(message, type) {
    const container = document.getElementById('event-notifications') || createNotificationContainer();

    const notification = document.createElement('div');
    notification.className = `event-notification ${type}`;
    notification.innerHTML = `
        <span class="event-icon">${type === 'buy' ? '🌟' : '💥'}</span>
        <span class="event-message">${message}</span>
    `;

    container.appendChild(notification);

    // Animate in
    setTimeout(() => notification.classList.add('visible'), 10);

    // Remove after delay
    setTimeout(() => {
        notification.classList.remove('visible');
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

function createNotificationContainer() {
    const container = document.createElement('div');
    container.id = 'event-notifications';
    container.style.cssText = `
        position: fixed;
        top: 100px;
        right: 20px;
        z-index: 1000;
        display: flex;
        flex-direction: column;
        gap: 10px;
    `;
    document.body.appendChild(container);
    return container;
}

/**
 * Update active animations
 */
function updateAnimations(deltaTime) {
    for (let i = activeAnimations.length - 1; i >= 0; i--) {
        const anim = activeAnimations[i];
        anim.progress += deltaTime / anim.duration;

        if (anim.type === 'birth') {
            updateBirthAnimation(anim);
        } else if (anim.type === 'collision') {
            updateCollisionAnimation(anim);
        }

        if (anim.progress >= 1) {
            if (anim.onComplete) anim.onComplete();
            activeAnimations.splice(i, 1);
        }
    }
}

function updateBirthAnimation(anim) {
    const positions = anim.particles.geometry.attributes.position.array;
    const t = anim.progress;
    const eased = 1 - Math.pow(1 - t, 3);

    for (let i = 0; i < positions.length / 3; i++) {
        const i3 = i * 3;
        const vel = anim.velocities[i];

        // Move toward target with easing
        positions[i3] += vel.x * (1 + eased * 3);
        positions[i3 + 1] += vel.y * (1 + eased * 3);
        positions[i3 + 2] += vel.z * (1 + eased * 3);
    }

    anim.particles.geometry.attributes.position.needsUpdate = true;
    anim.particles.material.opacity = 0.8 * (1 - t * 0.5);

    // Particles spiral inward
    anim.particles.rotation.y += 0.05;
}

function updateCollisionAnimation(anim) {
    const t = anim.progress;

    if (t < 0.4) {
        // Approach phase
        const approachT = t / 0.4;
        const eased = approachT * approachT;

        anim.asteroid.position.lerpVectors(anim.asteroidStart, anim.planetPos, eased);
        anim.asteroid.rotation.x += 0.1;
        anim.asteroid.rotation.y += 0.15;

    } else if (t < 0.5) {
        // Impact phase
        const impactT = (t - 0.4) / 0.1;

        // Hide asteroid
        anim.asteroid.visible = impactT < 0.5;

        // Show debris explosion
        anim.debris.material.opacity = impactT;

        // Planet flash
        if (anim.planetMesh && anim.planetMesh.material) {
            anim.planetMesh.material.emissiveIntensity = 0.5 + impactT * 0.5;
        }

    } else {
        // Explosion phase
        const explosionT = (t - 0.5) / 0.5;

        anim.asteroid.visible = false;

        // Debris expands outward
        const debrisPositions = anim.debris.geometry.attributes.position.array;
        for (let i = 0; i < debrisPositions.length / 3; i++) {
            const i3 = i * 3;
            const vel = anim.debrisVelocities[i];

            debrisPositions[i3] += vel.x;
            debrisPositions[i3 + 1] += vel.y;
            debrisPositions[i3 + 2] += vel.z;
        }
        anim.debris.geometry.attributes.position.needsUpdate = true;
        anim.debris.material.opacity = 0.8 * (1 - explosionT);

        // Planet returns to normal
        if (anim.planetMesh && anim.planetMesh.material) {
            anim.planetMesh.material.emissiveIntensity = 0.15 + (1 - explosionT) * 0.35;
        }
    }
}

// ==================== TIMELINE PLAYBACK ====================

function setupPlaybackControls() {
    // Add playback controls to timeline section
    const timelineSection = document.querySelector('.timeline-section');
    if (!timelineSection) return;

    const playbackControls = document.createElement('div');
    playbackControls.className = 'playback-controls';
    playbackControls.innerHTML = `
        <button id="play-btn" class="control-btn" title="Play/Pause">
            <span class="play-icon">▶</span>
            <span class="pause-icon" style="display:none">⏸</span>
        </button>
        <button id="speed-btn" class="control-btn" title="Speed">1x</button>
        <button id="restart-btn" class="control-btn" title="Restart">⏮</button>
        <div class="playback-info">
            <span id="frame-counter">0 / 0</span>
        </div>
    `;

    timelineSection.insertBefore(playbackControls, timelineSection.querySelector('.timeline-markers'));

    // Event listeners
    document.getElementById('play-btn').addEventListener('click', togglePlayback);
    document.getElementById('speed-btn').addEventListener('click', cycleSpeed);
    document.getElementById('restart-btn').addEventListener('click', restartPlayback);
}

function togglePlayback() {
    isPlaying = !isPlaying;

    const playIcon = document.querySelector('.play-icon');
    const pauseIcon = document.querySelector('.pause-icon');

    if (isPlaying) {
        playIcon.style.display = 'none';
        pauseIcon.style.display = 'inline';
        lastPlaybackTime = Date.now();
    } else {
        playIcon.style.display = 'inline';
        pauseIcon.style.display = 'none';
    }
}

function cycleSpeed() {
    const speeds = [0.5, 1, 2, 4];
    const currentIndex = speeds.indexOf(playbackSpeed);
    playbackSpeed = speeds[(currentIndex + 1) % speeds.length];

    document.getElementById('speed-btn').textContent = `${playbackSpeed}x`;
}

function restartPlayback() {
    playbackFrameIndex = 0;
    timelinePosition = 0;
    document.getElementById('timeline-slider').value = 0;

    // Reset all realities to initial state
    realities.forEach(reality => {
        if (reality.solarSystem) {
            // Remove all planets
            Object.values(reality.planets || {}).forEach(planet => {
                reality.solarSystem.remove(planet);
            });
            reality.planets = {};
        }
    });

    updateTimeline();
}

function updatePlayback() {
    if (!isPlaying) return;

    const now = Date.now();
    const deltaMs = now - lastPlaybackTime;
    lastPlaybackTime = now;

    // Advance timeline based on speed
    const framesPerSecond = 30 * playbackSpeed;
    const frameDelta = (deltaMs / 1000) * framesPerSecond;

    // Get max frames from first reality with frames
    const maxFrames = realities.reduce((max, r) => Math.max(max, r.frames?.length || 0), 0);

    if (maxFrames > 0) {
        playbackFrameIndex = Math.min(playbackFrameIndex + frameDelta, maxFrames - 1);

        // Update slider
        timelinePosition = playbackFrameIndex / maxFrames;
        document.getElementById('timeline-slider').value = timelinePosition * 100;

        // Update frame counter
        document.getElementById('frame-counter').textContent =
            `${Math.floor(playbackFrameIndex)} / ${maxFrames}`;

        // Process events for current frame
        processPlaybackFrame(Math.floor(playbackFrameIndex));

        // Update timeline display
        updateTimeline();

        // Stop at end
        if (playbackFrameIndex >= maxFrames - 1) {
            isPlaying = false;
            document.querySelector('.play-icon').style.display = 'inline';
            document.querySelector('.pause-icon').style.display = 'none';
        }
    }
}

function processPlaybackFrame(frameIndex) {
    realities.forEach(reality => {
        if (!reality.frames || !reality.events) return;

        const frame = reality.frames[frameIndex];
        if (!frame) return;

        // Check for events on this date
        const frameDate = frame.date;
        const eventsOnDate = reality.events.filter(e => {
            const eventDate = e.timestamp?.split('T')[0] || e.timestamp?.split(' ')[0];
            return eventDate === frameDate;
        });

        // Trigger animations for events we haven't processed
        eventsOnDate.forEach(event => {
            if (event._processed) return;
            event._processed = true;

            const data = event.data || {};

            if (event.event_type === 'TRADE') {
                if (data.action === 'BUY') {
                    // Planet birth!
                    createPlanetBirthAnimation(
                        reality,
                        data.ticker,
                        data.shares,
                        data.price
                    );
                } else if (data.action === 'SELL') {
                    // Asteroid collision!
                    createAsteroidCollisionAnimation(
                        reality,
                        data.ticker,
                        data.shares,
                        data.price
                    );
                }
            } else if (event.event_type === 'DEPOSIT') {
                // Sun grows brighter momentarily
                flashSun(reality, 0x00ff88);
            } else if (event.event_type === 'WITHDRAWAL') {
                // Sun dims momentarily
                flashSun(reality, 0xff4444);
            } else if (event.event_type === 'DIVIDEND') {
                // Sparkle effect on planet
                createDividendSparkle(reality, data.ticker);
            }
        });

        // Update solar system scale based on frame value
        if (frame.total_value && reality.solarSystem) {
            const baseValue = reality.state?.total_value || 500000;
            const scale = Math.sqrt(frame.total_value / baseValue);
            reality.solarSystem.scale.setScalar(Math.max(0.5, Math.min(1.5, scale)));

            // Update value label
            reality.solarSystem.traverse(obj => {
                if (obj.userData.valueLabel) {
                    updateValueLabelSprite(obj, frame.total_value);
                }
            });
        }
    });
}

function flashSun(reality, color) {
    if (!reality.solarSystem) return;

    reality.solarSystem.traverse(obj => {
        if (obj.userData.type === 'sun') {
            const originalColor = obj.material.color.getHex();
            obj.material.color.setHex(color);

            setTimeout(() => {
                obj.material.color.setHex(originalColor);
            }, 300);
        }
    });
}

function createDividendSparkle(reality, ticker) {
    const planet = reality.planets?.[ticker];
    if (!planet) return;

    // Create sparkle particles
    const sparkleCount = 30;
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(sparkleCount * 3);

    for (let i = 0; i < sparkleCount; i++) {
        const angle = (i / sparkleCount) * Math.PI * 2;
        const radius = 10 + Math.random() * 5;
        positions[i * 3] = Math.cos(angle) * radius;
        positions[i * 3 + 1] = (Math.random() - 0.5) * 10;
        positions[i * 3 + 2] = Math.sin(angle) * radius;
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

    const material = new THREE.PointsMaterial({
        color: 0xffd700,
        size: 3,
        transparent: true,
        opacity: 1,
        blending: THREE.AdditiveBlending
    });

    const sparkles = new THREE.Points(geometry, material);
    planet.add(sparkles);

    // Animate
    const startTime = Date.now();
    const animate = () => {
        const elapsed = (Date.now() - startTime) / 1000;
        if (elapsed < 1) {
            material.opacity = 1 - elapsed;
            sparkles.rotation.y += 0.1;
            sparkles.scale.setScalar(1 + elapsed * 0.5);
            requestAnimationFrame(animate);
        } else {
            planet.remove(sparkles);
            geometry.dispose();
            material.dispose();
        }
    };
    animate();
}

function updateValueLabelSprite(sprite, value) {
    // Update the texture with new value
    const canvas = document.createElement('canvas');
    canvas.width = 256;
    canvas.height = 64;
    const ctx = canvas.getContext('2d');

    ctx.font = 'bold 20px monospace';
    ctx.textAlign = 'center';
    ctx.fillStyle = '#00ff88';
    ctx.fillText(`$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, 128, 40);

    sprite.material.map.dispose();
    sprite.material.map = new THREE.CanvasTexture(canvas);
    sprite.material.map.needsUpdate = true;
}

// ==================== EXISTING FUNCTIONS ====================

function createConnections() {
    if (realities.length < 2) return;

    const mainReality = realities[0];
    const mainPos = mainReality.basePosition;

    for (let i = 1; i < realities.length; i++) {
        const altPos = realities[i].basePosition;

        const points = [];
        points.push(mainPos.clone().add(new THREE.Vector3(0, -30, 0)));

        // Create curved path
        const mid = mainPos.clone().lerp(altPos, 0.5);
        mid.y = -50;
        points.push(mid);

        points.push(altPos.clone().add(new THREE.Vector3(0, -30, 0)));

        const curve = new THREE.QuadraticBezierCurve3(points[0], points[1], points[2]);
        const curvePoints = curve.getPoints(30);
        const geometry = new THREE.BufferGeometry().setFromPoints(curvePoints);

        const material = new THREE.LineBasicMaterial({
            color: 0x9333ea,
            transparent: true,
            opacity: 0.2
        });

        const line = new THREE.Line(geometry, material);
        line.userData.connection = true;
        scene.add(line);
    }
}

function updateRealityPanel() {
    const panel = document.getElementById('reality-panel');
    panel.innerHTML = '';

    realities.forEach((reality, index) => {
        const state = reality.state || {};
        const totalValue = state.total_value || state.portfolio_value || 0;
        const isMain = reality.isMain;

        // Calculate change vs main reality
        const mainValue = realities[0]?.state?.total_value || realities[0]?.state?.portfolio_value || totalValue;
        const change = totalValue - mainValue;
        const changePct = mainValue > 0 ? ((change / mainValue) * 100) : 0;

        const card = document.createElement('div');
        card.className = `reality-card ${isMain ? 'reality-main' : 'reality-alt'} ${selectedReality === index ? 'active' : ''}`;
        card.dataset.index = index;

        card.innerHTML = `
            <div class="reality-name">
                ${reality.name}
                <span class="reality-badge">${isMain ? 'Main' : 'Alt'}</span>
            </div>
            <div class="reality-value">$${totalValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
            ${!isMain ? `
                <div class="reality-change ${change >= 0 ? 'positive' : 'negative'}">
                    ${change >= 0 ? '+' : ''}$${change.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    (${changePct >= 0 ? '+' : ''}${changePct.toFixed(1)}%)
                </div>
            ` : ''}
            <div class="reality-description">${reality.description || ''}</div>
            <div class="reality-stats">
                <span>${reality.events?.length || 0} events</span>
                <span>${Object.keys(reality.planets || {}).length} holdings</span>
            </div>
        `;

        card.addEventListener('click', () => selectReality(index));
        panel.appendChild(card);
    });
}

function selectReality(index) {
    selectedReality = selectedReality === index ? null : index;

    // Update card styles
    document.querySelectorAll('.reality-card').forEach((card, i) => {
        card.classList.toggle('active', i === selectedReality);
    });

    // Animate camera to selected reality
    if (selectedReality !== null) {
        const reality = realities[selectedReality];
        const pos = reality.basePosition;

        animateCameraTo(
            pos.x + 50,
            100,
            pos.z + 150,
            pos.x,
            0,
            pos.z
        );

        showComparison(selectedReality);
    } else {
        // Zoom out to overview
        animateCameraTo(0, 300, 500, 0, 0, 0);
        hideComparison();
    }
}

function animateCameraTo(x, y, z, lookX, lookY, lookZ) {
    const startPos = camera.position.clone();
    const endPos = new THREE.Vector3(x, y, z);
    const startTarget = controls.target.clone();
    const endTarget = new THREE.Vector3(lookX, lookY, lookZ);

    let progress = 0;
    const duration = 1000;
    const startTime = Date.now();

    function update() {
        const elapsed = Date.now() - startTime;
        progress = Math.min(1, elapsed / duration);

        // Ease out cubic
        const t = 1 - Math.pow(1 - progress, 3);

        camera.position.lerpVectors(startPos, endPos, t);
        controls.target.lerpVectors(startTarget, endTarget, t);
        controls.update();

        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }

    update();
}

function showComparison(index) {
    if (index === 0) {
        hideComparison();
        return;
    }

    const panel = document.getElementById('comparison-panel');
    const content = document.getElementById('comparison-content');

    const mainState = realities[0].state;
    const altState = realities[index].state;

    const mainValue = mainState.total_value || mainState.portfolio_value || 0;
    const altValue = altState.total_value || altState.portfolio_value || 0;
    const diff = altValue - mainValue;

    content.innerHTML = `
        <div class="comparison-row">
            <span class="comparison-label">Portfolio Value</span>
            <div class="comparison-values">
                <span class="comparison-value" style="color: #06b6d4">$${mainValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                <span class="comparison-arrow">→</span>
                <span class="comparison-value" style="color: #9333ea">$${altValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
            </div>
        </div>
        <div class="comparison-row">
            <span class="comparison-label">Difference</span>
            <span class="comparison-diff ${diff >= 0 ? 'positive' : 'negative'}">
                ${diff >= 0 ? '+' : ''}$${diff.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </span>
        </div>
        <div class="comparison-row">
            <span class="comparison-label">Divergence</span>
            <span class="comparison-value">${realities[index].divergence_point || 'Unknown'}</span>
        </div>
    `;

    panel.classList.add('visible');
}

function hideComparison() {
    document.getElementById('comparison-panel').classList.remove('visible');
}

function setupEventListeners() {
    // Timeline slider - now centered on present
    const slider = document.getElementById('timeline-slider');
    slider.value = 50; // Start at present (center)
    slider.addEventListener('input', (e) => {
        timelinePosition = e.target.value / 100;

        // Also update playback frame index
        const maxFrames = realities.reduce((max, r) => Math.max(max, r.frames?.length || 0), 0);
        playbackFrameIndex = timelinePosition * maxFrames;

        updateTimeline();
    });

    // Window resize
    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });

    // Click detection
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();

    renderer.domElement.addEventListener('click', (event) => {
        mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
        mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

        raycaster.setFromCamera(mouse, camera);

        const clickableObjects = [];
        realities.forEach(r => {
            if (r.solarSystem) {
                r.solarSystem.traverse(obj => {
                    if (obj.userData.type === 'sun') {
                        clickableObjects.push(obj);
                    }
                });
            }
        });

        const intersects = raycaster.intersectObjects(clickableObjects);
        if (intersects.length > 0) {
            const reality = intersects[0].object.userData.reality;
            const index = realities.findIndex(r => r.id === reality.id);
            if (index !== -1) {
                selectReality(index);
            }
        }
    });

    // Update timeline markers
    updateTimelineMarkers();
}

function updateTimelineMarkers() {
    const markers = document.querySelector('.timeline-markers');
    if (!markers) return;

    markers.innerHTML = `
        <span>Start</span>
        <span>25%</span>
        <span style="color: #9333ea; font-weight: bold;">Present</span>
        <span>75%</span>
        <span>End</span>
    `;
}

function updateTimeline() {
    const dateLabel = document.getElementById('timeline-date');
    const sentimentOverlay = document.getElementById('sentiment-overlay');

    // Calculate date based on frame index
    const maxFrames = realities.reduce((max, r) => Math.max(max, r.frames?.length || 0), 0);
    const frameIndex = Math.floor(timelinePosition * maxFrames);

    // Get date from first reality with frames
    let targetDate = new Date();
    for (const reality of realities) {
        if (reality.frames?.[frameIndex]?.date) {
            targetDate = new Date(reality.frames[frameIndex].date);
            break;
        }
    }

    dateLabel.textContent = targetDate.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });

    // Check for nearby macro events
    checkMacroEvents(targetDate);

    // Update sentiment overlay based on projection data
    updateSentimentOverlay(targetDate);

    // Update visualizations based on timeline
    updateRealityValues();
}

function checkMacroEvents(currentDate) {
    const popup = document.getElementById('macro-event-popup');
    const threshold = 15 * 24 * 60 * 60 * 1000; // 15 days in ms

    let nearestEvent = null;
    let nearestDistance = Infinity;

    macroEvents.forEach((event, index) => {
        const eventDate = new Date(event.date);
        const distance = Math.abs(eventDate.getTime() - currentDate.getTime());

        if (distance < threshold && distance < nearestDistance) {
            nearestEvent = event;
            nearestDistance = distance;
            currentMacroEventIndex = index;
        }
    });

    if (nearestEvent) {
        showMacroEventPopup(nearestEvent);
    } else {
        popup.classList.remove('visible');
        currentMacroEventIndex = -1;
    }
}

function showMacroEventPopup(event) {
    const popup = document.getElementById('macro-event-popup');
    const dateEl = document.getElementById('event-date');
    const titleEl = document.getElementById('event-title');
    const descEl = document.getElementById('event-description');
    const impactEl = document.getElementById('event-impact');

    dateEl.textContent = new Date(event.date).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
    titleEl.textContent = event.title;
    descEl.textContent = event.description;

    impactEl.textContent = event.impact === 'positive' ? 'Bullish Impact' : 'Bearish Impact';
    impactEl.className = `macro-event-impact ${event.impact}`;

    popup.classList.remove('bullish', 'bearish', 'neutral');
    popup.classList.add(event.impact === 'positive' ? 'bullish' : 'bearish');
    popup.classList.add('visible');
}

function updateSentimentOverlay(currentDate) {
    const overlay = document.getElementById('sentiment-overlay');
    const now = new Date();

    // Calculate sentiment based on timeline position and projection data
    let sentiment = 'neutral';
    let intensity = 0;

    if (projectionData?.frames) {
        // Find nearest frame
        const targetDateStr = currentDate.toISOString().split('T')[0];
        const nearestFrame = projectionData.frames.find(f => f.date === targetDateStr) ||
            projectionData.frames.reduce((nearest, frame) => {
                const dist = Math.abs(new Date(frame.date) - currentDate);
                const nearestDist = Math.abs(new Date(nearest.date) - currentDate);
                return dist < nearestDist ? frame : nearest;
            }, projectionData.frames[0]);

        if (nearestFrame) {
            const baseValue = projectionData.current_state?.total_value || 500000;
            const change = (nearestFrame.total_value - baseValue) / baseValue;

            if (change > 0.1) {
                sentiment = 'bullish';
                intensity = Math.min(0.3, change);
            } else if (change < -0.1) {
                sentiment = 'bearish';
                intensity = Math.min(0.3, Math.abs(change));
            }
        }
    }

    overlay.classList.remove('bullish', 'bearish');
    if (sentiment !== 'neutral') {
        overlay.classList.add(sentiment);
        overlay.style.opacity = intensity;
    } else {
        overlay.style.opacity = 0;
    }
}

function updateRealityValues() {
    // Animate reality values based on timeline position
    realities.forEach((reality, index) => {
        if (reality.solarSystem && reality.frames) {
            const frameIndex = Math.floor(timelinePosition * reality.frames.length);
            const frame = reality.frames[frameIndex];

            if (frame) {
                // Scale solar system based on value at this frame
                const baseValue = reality.state?.total_value || 500000;
                const ratio = frame.total_value / baseValue;
                reality.solarSystem.scale.setScalar(Math.max(0.5, Math.min(1.5, Math.sqrt(ratio))));
            }
        }
    });
}

function setupCreateModal() {
    const createBtn = document.getElementById('create-btn');
    const modal = document.getElementById('create-modal');
    const cancelBtn = document.getElementById('cancel-create');
    const submitBtn = document.getElementById('submit-create');
    const addPurchaseBtn = document.getElementById('add-purchase-btn');

    createBtn.addEventListener('click', () => {
        modal.classList.add('visible');
    });

    cancelBtn.addEventListener('click', () => {
        modal.classList.remove('visible');
    });

    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.remove('visible');
        }
    });

    addPurchaseBtn.addEventListener('click', () => {
        addPurchaseRow();
    });

    submitBtn.addEventListener('click', async () => {
        await createReality();
    });

    // Quick scenario buttons
    document.querySelectorAll('.scenario-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const scenario = btn.dataset.scenario;
            await createQuickScenario(scenario);
        });
    });
}

function addPurchaseRow() {
    const container = document.getElementById('purchases-container');
    const row = document.createElement('div');
    row.className = 'purchase-row';
    row.innerHTML = `
        <input type="text" class="form-input" placeholder="Ticker (e.g., NVDA)" data-field="ticker">
        <input type="number" class="form-input" placeholder="Shares" data-field="shares" min="1">
        <button class="remove-purchase" onclick="removePurchase(this)">✕</button>
    `;
    container.appendChild(row);
}

// Make removePurchase global
window.removePurchase = function(btn) {
    const row = btn.closest('.purchase-row');
    const container = document.getElementById('purchases-container');
    if (container.children.length > 1) {
        row.remove();
    }
};

async function createReality() {
    const name = document.getElementById('reality-name').value;
    const description = document.getElementById('reality-description').value;
    const startDate = document.getElementById('reality-start-date').value;
    const startingCash = parseFloat(document.getElementById('reality-cash').value);

    // Gather purchases
    const purchases = [];
    document.querySelectorAll('.purchase-row').forEach(row => {
        const ticker = row.querySelector('[data-field="ticker"]').value.toUpperCase();
        const shares = parseInt(row.querySelector('[data-field="shares"]').value);
        if (ticker && shares > 0) {
            purchases.push({ ticker, shares });
        }
    });

    if (!name) {
        alert('Please enter a reality name');
        return;
    }

    if (purchases.length === 0) {
        alert('Please add at least one stock purchase');
        return;
    }

    try {
        const response = await fetch('/api/alt-history', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name,
                description: description || `What-if scenario starting ${startDate}`,
                modifications: purchases.map(p => ({
                    type: 'add_trade',
                    ticker: p.ticker,
                    action: 'BUY',
                    shares: p.shares,
                    timestamp: startDate
                })),
                use_llm: true
            })
        });

        if (response.ok) {
            const result = await response.json();
            console.log('Created reality:', result);

            // Close modal and refresh
            document.getElementById('create-modal').classList.remove('visible');
            location.reload();
        } else {
            const error = await response.json();
            alert('Failed to create reality: ' + (error.detail || 'Unknown error'));
        }
    } catch (e) {
        console.error('Error creating reality:', e);
        alert('Error creating reality: ' + e.message);
    }
}

async function createQuickScenario(scenario) {
    try {
        const response = await fetch(`/api/alt-history/what-if/${scenario === 'tech-bull' ? 'doubled-position' : 'never-bought'}?ticker=TSLA`, {
            method: 'POST'
        });

        if (response.ok) {
            location.reload();
        }
    } catch (e) {
        console.error('Error creating quick scenario:', e);
    }
}

let lastFrameTime = 0;

function animate(currentTime = 0) {
    requestAnimationFrame(animate);

    const deltaTime = (currentTime - lastFrameTime) / 1000;
    lastFrameTime = currentTime;

    animationTime += 0.016;

    // Update playback
    updatePlayback();

    // Update active animations
    updateAnimations(deltaTime || 0.016);

    // Animate planets
    realities.forEach(reality => {
        if (reality.solarSystem) {
            reality.solarSystem.traverse(obj => {
                if (obj.userData.orbitRadius) {
                    obj.userData.orbitAngle += obj.userData.orbitSpeed * 0.02;
                    obj.position.x = Math.cos(obj.userData.orbitAngle) * obj.userData.orbitRadius;
                    obj.position.z = Math.sin(obj.userData.orbitAngle) * obj.userData.orbitRadius;
                }
            });

            // Gentle bobbing
            reality.solarSystem.position.y = Math.sin(animationTime * 0.5 + reality.solarSystem.userData.index) * 2;
        }
    });

    // Pulse selected reality
    if (selectedReality !== null && realities[selectedReality]?.solarSystem) {
        const system = realities[selectedReality].solarSystem;
        const pulse = 1 + Math.sin(animationTime * 3) * 0.05;
        system.children[0].scale.setScalar(pulse);
    }

    // Update distant background systems
    if (distantSystems.length > 0) {
        updateDistantSystems();
    }

    controls.update();
    renderer.render(scene, camera);
}

function hideLoading() {
    const loading = document.getElementById('loading');
    setTimeout(() => {
        loading.classList.add('hidden');
    }, 500);
}

// ==================== AMBIENT BACKGROUND ANIMATIONS ====================

let ambientInterval = null;
let isPortfolioGreen = true;

function startAmbientAnimations() {
    // Check portfolio status every 10 seconds
    updatePortfolioStatus();
    setInterval(updatePortfolioStatus, 10000);

    // Start ambient effects
    ambientInterval = setInterval(createAmbientEffect, 3000);
    createAmbientEffect(); // Create one immediately
}

function updatePortfolioStatus() {
    // Determine if portfolio is green or red based on main reality
    const mainReality = realities.find(r => r.isMain);
    if (mainReality?.state) {
        const totalGain = mainReality.state.holdings?.reduce((sum, h) => sum + (h.unrealized_gain || 0), 0) || 0;
        isPortfolioGreen = totalGain >= 0;
    }
}

function createAmbientEffect() {
    const container = document.getElementById('ambient-container');
    if (!container) return;

    // Random effect type
    const effectType = Math.random();

    if (effectType < 0.4) {
        // Comet flying across
        createAmbientComet(container);
    } else if (effectType < 0.7) {
        // Distant explosion/supernova
        createAmbientExplosion(container);
    } else {
        // Shooting star cluster
        createShootingStars(container);
    }
}

function createAmbientComet(container) {
    const comet = document.createElement('div');
    comet.className = 'ambient-comet';

    // Random starting position
    comet.style.top = `${Math.random() * 60}%`;
    comet.style.left = '-200px';

    // Color based on portfolio status
    if (isPortfolioGreen) {
        comet.style.background = 'linear-gradient(90deg, transparent, rgba(0,255,136,0.8), rgba(6,182,212,0.4), transparent)';
    } else {
        comet.style.background = 'linear-gradient(90deg, transparent, rgba(255,100,100,0.8), rgba(255,150,50,0.4), transparent)';
    }

    // Random angle
    const angle = -15 + Math.random() * 30;
    comet.style.transform = `rotate(${angle}deg)`;

    container.appendChild(comet);

    // Remove after animation
    setTimeout(() => comet.remove(), 3500);
}

function createAmbientExplosion(container) {
    const explosion = document.createElement('div');
    explosion.className = `ambient-explosion ${isPortfolioGreen ? 'good' : 'bad'}`;

    // Random position in the visible area (avoiding HUD areas)
    explosion.style.top = `${20 + Math.random() * 50}%`;
    explosion.style.left = `${20 + Math.random() * 60}%`;

    container.appendChild(explosion);

    // Remove after animation
    setTimeout(() => explosion.remove(), 2000);
}

function createShootingStars(container) {
    // Create a burst of 3-5 small shooting stars
    const count = 3 + Math.floor(Math.random() * 3);
    const startX = Math.random() * 80 + 10;
    const startY = Math.random() * 40;

    for (let i = 0; i < count; i++) {
        setTimeout(() => {
            const star = document.createElement('div');
            star.className = 'ambient-comet';
            star.style.width = '30px';
            star.style.height = '1px';
            star.style.top = `${startY + i * 3}%`;
            star.style.left = `${startX}%`;

            if (isPortfolioGreen) {
                star.style.background = 'linear-gradient(90deg, transparent, rgba(0,255,200,0.6), transparent)';
            } else {
                star.style.background = 'linear-gradient(90deg, transparent, rgba(255,100,100,0.6), transparent)';
            }

            star.style.animation = 'comet-fly 1.5s linear forwards';
            container.appendChild(star);

            setTimeout(() => star.remove(), 1500);
        }, i * 100);
    }
}

// ==================== THREE.JS AMBIENT EFFECTS ====================

let distantSystems = [];

function createDistantSolarSystems() {
    // Create small distant solar systems in the background
    const count = 8;

    for (let i = 0; i < count; i++) {
        const group = new THREE.Group();

        // Position far away
        const angle = (i / count) * Math.PI * 2;
        const distance = 800 + Math.random() * 400;
        const height = (Math.random() - 0.5) * 400;

        group.position.set(
            Math.cos(angle) * distance,
            height,
            Math.sin(angle) * distance
        );

        // Small dim sun
        const sunGeometry = new THREE.SphereGeometry(3, 16, 16);
        const sunColor = Math.random() > 0.5 ? 0xff6600 : 0x0066ff;
        const sunMaterial = new THREE.MeshBasicMaterial({
            color: sunColor,
            transparent: true,
            opacity: 0.4
        });
        const sun = new THREE.Mesh(sunGeometry, sunMaterial);
        group.add(sun);

        // A couple tiny planets
        for (let j = 0; j < 2; j++) {
            const planetGeometry = new THREE.SphereGeometry(0.5, 8, 8);
            const planetMaterial = new THREE.MeshBasicMaterial({
                color: 0x888888,
                transparent: true,
                opacity: 0.3
            });
            const planet = new THREE.Mesh(planetGeometry, planetMaterial);

            const orbitRadius = 5 + j * 4;
            const planetAngle = Math.random() * Math.PI * 2;
            planet.position.x = Math.cos(planetAngle) * orbitRadius;
            planet.position.z = Math.sin(planetAngle) * orbitRadius;
            planet.userData.orbitRadius = orbitRadius;
            planet.userData.orbitAngle = planetAngle;
            planet.userData.orbitSpeed = 0.01 / (j + 1);

            group.add(planet);
        }

        scene.add(group);
        distantSystems.push({
            group,
            originalColor: sunColor,
            sun
        });
    }
}

function updateDistantSystems() {
    // Animate distant systems and occasionally trigger events on them
    distantSystems.forEach((system, index) => {
        // Rotate planets
        system.group.traverse(obj => {
            if (obj.userData.orbitRadius) {
                obj.userData.orbitAngle += obj.userData.orbitSpeed;
                obj.position.x = Math.cos(obj.userData.orbitAngle) * obj.userData.orbitRadius;
                obj.position.z = Math.sin(obj.userData.orbitAngle) * obj.userData.orbitRadius;
            }
        });

        // Random events (very occasionally)
        if (Math.random() < 0.0005) {
            triggerDistantSystemEvent(system, index);
        }
    });
}

function triggerDistantSystemEvent(system, index) {
    // Event based on portfolio status
    if (isPortfolioGreen) {
        // Good event - nova/bright flash
        createDistantNova(system);
    } else {
        // Bad event - collapse/dimming
        createDistantCollapse(system);
    }
}

function createDistantNova(system) {
    // Bright flash effect on distant system
    const flashGeometry = new THREE.SphereGeometry(15, 16, 16);
    const flashMaterial = new THREE.MeshBasicMaterial({
        color: 0x00ff88,
        transparent: true,
        opacity: 0.6,
        blending: THREE.AdditiveBlending
    });
    const flash = new THREE.Mesh(flashGeometry, flashMaterial);
    system.group.add(flash);

    // Animate
    let progress = 0;
    const animate = () => {
        progress += 0.02;
        flash.scale.setScalar(1 + progress * 3);
        flashMaterial.opacity = 0.6 * (1 - progress);

        if (progress < 1) {
            requestAnimationFrame(animate);
        } else {
            system.group.remove(flash);
            flashGeometry.dispose();
            flashMaterial.dispose();
        }
    };
    animate();
}

function createDistantCollapse(system) {
    // System dims and shrinks
    const originalScale = system.group.scale.x;

    let progress = 0;
    const animate = () => {
        progress += 0.01;

        // Shrink
        const scale = originalScale * (1 - progress * 0.5);
        system.group.scale.setScalar(scale);

        // Dim
        system.sun.material.opacity = 0.4 * (1 - progress * 0.7);

        // Flash red
        if (progress < 0.3) {
            system.sun.material.color.setHex(0xff4444);
        }

        if (progress < 1) {
            requestAnimationFrame(animate);
        } else {
            // Restore
            setTimeout(() => {
                system.group.scale.setScalar(originalScale);
                system.sun.material.opacity = 0.4;
                system.sun.material.color.setHex(system.originalColor);
            }, 2000);
        }
    };
    animate();
}

// Initialize ambient effects after main init
setTimeout(() => {
    createDistantSolarSystems();
    startAmbientAnimations();
}, 1000);

// Start
init();
