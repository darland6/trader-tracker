import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

// Global state
let scene, camera, renderer, controls;
let planets = new Map();
let sun, starField;
let portfolioData = null;
let clock = new THREE.Clock();
let isDemoMode = false;

// Camera animation state
let cameraAnimation = {
    active: false,
    startPos: new THREE.Vector3(),
    endPos: new THREE.Vector3(),
    startTarget: new THREE.Vector3(),
    endTarget: new THREE.Vector3(),
    duration: 1.5,
    elapsed: 0,
    easing: t => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2 // easeInOutCubic
};

// Interaction state
let raycaster = new THREE.Raycaster();
let mouse = new THREE.Vector2();
let selectedPlanet = null;
let hoveredObject = null;

// Default camera position for system view
const DEFAULT_CAMERA_POS = new THREE.Vector3(0, 25, 50);
const DEFAULT_TARGET = new THREE.Vector3(0, 0, 0);

// Initialize scene
function init() {
    const container = document.getElementById('canvas-container');

    // Scene
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x050510);

    // Camera
    camera = new THREE.PerspectiveCamera(
        60,
        window.innerWidth / window.innerHeight,
        0.1,
        1000
    );
    camera.position.set(0, 20, 40);

    // Renderer
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;
    container.appendChild(renderer.domElement);

    // Controls
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.maxDistance = 80;
    controls.minDistance = 15;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.3;

    // Lights
    const ambientLight = new THREE.AmbientLight(0x404040, 0.3);
    scene.add(ambientLight);

    // Create star field
    createStarField();

    // Create central sun (portfolio total)
    createSun();

    // Handle resize
    window.addEventListener('resize', onWindowResize);

    // Handle click interactions
    renderer.domElement.addEventListener('click', onCanvasClick);
    renderer.domElement.addEventListener('mousemove', onCanvasMouseMove);

    // Start animation
    animate();
}

function createStarField() {
    const geometry = new THREE.BufferGeometry();
    const count = 8000;
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);

    for (let i = 0; i < count * 3; i += 3) {
        positions[i] = (Math.random() - 0.5) * 300;
        positions[i + 1] = (Math.random() - 0.5) * 300;
        positions[i + 2] = (Math.random() - 0.5) * 300;

        // Slight color variation
        const brightness = 0.5 + Math.random() * 0.5;
        colors[i] = brightness;
        colors[i + 1] = brightness;
        colors[i + 2] = brightness + Math.random() * 0.2;
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const material = new THREE.PointsMaterial({
        size: 0.2,
        sizeAttenuation: true,
        vertexColors: true,
        transparent: true,
        opacity: 0.8
    });

    starField = new THREE.Points(geometry, material);
    scene.add(starField);
}

function createSun() {
    // Create glowing sun
    const geometry = new THREE.SphereGeometry(4, 64, 64);

    // Sun texture - procedural
    const sunCanvas = document.createElement('canvas');
    sunCanvas.width = 512;
    sunCanvas.height = 512;
    const ctx = sunCanvas.getContext('2d');

    // Gradient for sun surface
    const gradient = ctx.createRadialGradient(256, 256, 0, 256, 256, 256);
    gradient.addColorStop(0, '#ffffff');
    gradient.addColorStop(0.2, '#ffee88');
    gradient.addColorStop(0.5, '#ffcc00');
    gradient.addColorStop(0.8, '#ff8800');
    gradient.addColorStop(1, '#ff4400');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, 512, 512);

    // Add some noise/turbulence
    for (let i = 0; i < 1000; i++) {
        const x = Math.random() * 512;
        const y = Math.random() * 512;
        const r = Math.random() * 20;
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, ${150 + Math.random() * 100}, 0, ${Math.random() * 0.3})`;
        ctx.fill();
    }

    const sunTexture = new THREE.CanvasTexture(sunCanvas);

    const material = new THREE.MeshBasicMaterial({
        map: sunTexture,
        transparent: true,
        opacity: 0.95
    });

    sun = new THREE.Mesh(geometry, material);
    scene.add(sun);

    // Outer glow layers
    for (let i = 1; i <= 3; i++) {
        const glowGeometry = new THREE.SphereGeometry(4 + i * 0.8, 32, 32);
        const glowMaterial = new THREE.MeshBasicMaterial({
            color: new THREE.Color(0xffaa00),
            transparent: true,
            opacity: 0.15 / i,
            side: THREE.BackSide
        });
        const glow = new THREE.Mesh(glowGeometry, glowMaterial);
        sun.add(glow);
    }

    // Point light from sun
    const sunLight = new THREE.PointLight(0xffdd88, 2, 150);
    sun.add(sunLight);
}

// Generate realistic planet texture
function createPlanetTexture(baseColor, isGain) {
    const canvas = document.createElement('canvas');
    canvas.width = 512;
    canvas.height = 256;
    const ctx = canvas.getContext('2d');

    // Base color
    const color = new THREE.Color(baseColor);
    ctx.fillStyle = `rgb(${Math.floor(color.r * 255)}, ${Math.floor(color.g * 255)}, ${Math.floor(color.b * 255)})`;
    ctx.fillRect(0, 0, 512, 256);

    // Add bands/stripes like gas giants
    const bandCount = 8 + Math.floor(Math.random() * 8);
    for (let i = 0; i < bandCount; i++) {
        const y = (i / bandCount) * 256;
        const height = 256 / bandCount * (0.5 + Math.random());
        const lightness = 0.7 + Math.random() * 0.6;

        ctx.fillStyle = `rgba(${Math.floor(color.r * 255 * lightness)}, ${Math.floor(color.g * 255 * lightness)}, ${Math.floor(color.b * 255 * lightness)}, 0.5)`;
        ctx.fillRect(0, y, 512, height);
    }

    // Add swirls/storms
    for (let i = 0; i < 15; i++) {
        const x = Math.random() * 512;
        const y = Math.random() * 256;
        const rx = 20 + Math.random() * 40;
        const ry = 10 + Math.random() * 20;

        ctx.save();
        ctx.translate(x, y);
        ctx.rotate(Math.random() * Math.PI);
        ctx.beginPath();
        ctx.ellipse(0, 0, rx, ry, 0, 0, Math.PI * 2);

        const stormColor = isGain ?
            `rgba(100, 255, 150, ${0.2 + Math.random() * 0.3})` :
            `rgba(255, 100, 100, ${0.2 + Math.random() * 0.3})`;
        ctx.fillStyle = stormColor;
        ctx.fill();
        ctx.restore();
    }

    // Add some crater-like spots
    for (let i = 0; i < 30; i++) {
        const x = Math.random() * 512;
        const y = Math.random() * 256;
        const r = 3 + Math.random() * 15;

        const gradient = ctx.createRadialGradient(x, y, 0, x, y, r);
        gradient.addColorStop(0, `rgba(0, 0, 0, ${0.1 + Math.random() * 0.2})`);
        gradient.addColorStop(0.5, `rgba(0, 0, 0, ${0.05 + Math.random() * 0.1})`);
        gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');

        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fillStyle = gradient;
        ctx.fill();
    }

    return new THREE.CanvasTexture(canvas);
}

// Create atmosphere/glow for planet
function createAtmosphere(radius, isGain, intensity) {
    const group = new THREE.Group();

    // Inner glow
    const glowColor = isGain ? 0x00ff88 : 0xff4444;
    const glowIntensity = 0.3 + intensity * 0.4;

    for (let i = 1; i <= 2; i++) {
        const glowGeometry = new THREE.SphereGeometry(radius + i * 0.15, 32, 32);
        const glowMaterial = new THREE.MeshBasicMaterial({
            color: glowColor,
            transparent: true,
            opacity: glowIntensity / (i * 1.5),
            side: THREE.BackSide
        });
        const glow = new THREE.Mesh(glowGeometry, glowMaterial);
        group.add(glow);
    }

    return group;
}

// Create momentum particles around planet
function createMomentumParticles(radius, momentum) {
    const particleCount = Math.floor(50 + Math.abs(momentum) * 100);
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);

    const isPositive = momentum >= 0;
    const color = isPositive ? new THREE.Color(0x00ff88) : new THREE.Color(0xff4444);

    for (let i = 0; i < particleCount * 3; i += 3) {
        // Particles orbit around the planet
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.random() * Math.PI * 2;
        const r = radius + 0.3 + Math.random() * 1.5;

        positions[i] = r * Math.sin(theta) * Math.cos(phi);
        positions[i + 1] = r * Math.sin(theta) * Math.sin(phi);
        positions[i + 2] = r * Math.cos(theta);

        colors[i] = color.r;
        colors[i + 1] = color.g;
        colors[i + 2] = color.b;
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const material = new THREE.PointsMaterial({
        size: 0.08,
        vertexColors: true,
        transparent: true,
        opacity: 0.6 + Math.abs(momentum) * 0.4,
        blending: THREE.AdditiveBlending
    });

    return new THREE.Points(geometry, material);
}

// Create Cash "planet" with moons representing breakdown
function createCashPlanet(cashBreakdown, portfolioTotal) {
    const { total, secured_put_collateral, tax_reserve, available } = cashBreakdown;

    // Calculate size based on total cash relative to portfolio
    const sizeRatio = total / portfolioTotal;
    const radius = 1.0 + sizeRatio * 6; // Similar sizing to stock planets

    // Create golden cash planet
    const geometry = new THREE.SphereGeometry(radius, 64, 64);

    // Create golden texture
    const canvas = document.createElement('canvas');
    canvas.width = 512;
    canvas.height = 256;
    const ctx = canvas.getContext('2d');

    // Golden gradient base
    const gradient = ctx.createLinearGradient(0, 0, 512, 256);
    gradient.addColorStop(0, '#ffd700');
    gradient.addColorStop(0.3, '#ffec8b');
    gradient.addColorStop(0.5, '#ffd700');
    gradient.addColorStop(0.7, '#daa520');
    gradient.addColorStop(1, '#b8860b');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, 512, 256);

    // Add metallic sheen effects
    for (let i = 0; i < 20; i++) {
        const x = Math.random() * 512;
        const y = Math.random() * 256;
        const r = 30 + Math.random() * 50;
        const spotGradient = ctx.createRadialGradient(x, y, 0, x, y, r);
        spotGradient.addColorStop(0, 'rgba(255, 255, 200, 0.4)');
        spotGradient.addColorStop(0.5, 'rgba(255, 215, 0, 0.2)');
        spotGradient.addColorStop(1, 'rgba(184, 134, 11, 0)');
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fillStyle = spotGradient;
        ctx.fill();
    }

    const texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;

    const material = new THREE.MeshStandardMaterial({
        map: texture,
        metalness: 0.7,
        roughness: 0.3,
        emissive: 0x332200,
        emissiveIntensity: 0.3
    });

    const planet = new THREE.Mesh(geometry, material);

    // Create planet group
    const planetGroup = new THREE.Group();
    planetGroup.add(planet);

    // Add golden glow
    for (let i = 1; i <= 2; i++) {
        const glowGeometry = new THREE.SphereGeometry(radius + i * 0.2, 32, 32);
        const glowMaterial = new THREE.MeshBasicMaterial({
            color: 0xffd700,
            transparent: true,
            opacity: 0.15 / i,
            side: THREE.BackSide
        });
        const glow = new THREE.Mesh(glowGeometry, glowMaterial);
        planetGroup.add(glow);
    }

    // Create rings showing the cash breakdown proportions
    if (total > 0) {
        // Outer ring: Total cash (gold)
        const ringInner = radius + 0.4;
        const ringOuter = radius + 0.8;

        // Available cash ring (green) - the usable portion
        const availablePct = available / total;
        if (availablePct > 0.01) {
            const availableRing = createPartialRing(ringInner, ringOuter, 0, availablePct * Math.PI * 2, 0x00ff88);
            availableRing.rotation.x = Math.PI / 2;
            planetGroup.add(availableRing);
        }

        // Collateral ring (orange) - locked for puts
        const collateralPct = secured_put_collateral / total;
        if (collateralPct > 0.01) {
            const collateralRing = createPartialRing(ringInner, ringOuter,
                availablePct * Math.PI * 2,
                (availablePct + collateralPct) * Math.PI * 2,
                0xff8c00);
            collateralRing.rotation.x = Math.PI / 2;
            planetGroup.add(collateralRing);
        }

        // Tax reserve ring (red) - set aside for taxes
        const taxPct = tax_reserve / total;
        if (taxPct > 0.01) {
            const taxRing = createPartialRing(ringInner, ringOuter,
                (availablePct + collateralPct) * Math.PI * 2,
                Math.PI * 2,
                0xff4444);
            taxRing.rotation.x = Math.PI / 2;
            planetGroup.add(taxRing);
        }
    }

    // Create moons for each cash component
    const moonData = [
        { name: 'Available', value: available, color: 0x00ff88, angle: 0 },
        { name: 'Collateral', value: secured_put_collateral, color: 0xff8c00, angle: Math.PI * 0.7 },
        { name: 'Tax Reserve', value: tax_reserve, color: 0xff4444, angle: Math.PI * 1.4 }
    ];

    moonData.forEach((moon, idx) => {
        if (moon.value > 0) {
            const moonRadius = 0.2 + (moon.value / total) * 0.6;
            const moonGeometry = new THREE.SphereGeometry(moonRadius, 32, 32);
            const moonMaterial = new THREE.MeshStandardMaterial({
                color: moon.color,
                metalness: 0.3,
                roughness: 0.6,
                emissive: moon.color,
                emissiveIntensity: 0.2
            });
            const moonMesh = new THREE.Mesh(moonGeometry, moonMaterial);

            // Position moon in orbit around cash planet
            const moonOrbitRadius = radius + 1.5 + idx * 0.5;
            moonMesh.position.x = Math.cos(moon.angle) * moonOrbitRadius;
            moonMesh.position.z = Math.sin(moon.angle) * moonOrbitRadius;
            moonMesh.position.y = (Math.random() - 0.5) * 0.5;

            moonMesh.userData = {
                type: 'cash-moon',
                name: moon.name,
                value: moon.value,
                orbitRadius: moonOrbitRadius,
                orbitAngle: moon.angle,
                orbitSpeed: 0.003 + idx * 0.001
            };

            planetGroup.add(moonMesh);
        }
    });

    // Position cash planet - place it at a distinct orbit
    const orbitRadius = 8; // Inner orbit, close to sun (cash is central)
    const angle = Math.PI * 0.25; // Offset from other planets
    planetGroup.position.x = Math.cos(angle) * orbitRadius;
    planetGroup.position.z = Math.sin(angle) * orbitRadius;
    planetGroup.position.y = 0;

    // Store data
    planetGroup.userData = {
        type: 'cash-planet',
        ticker: 'CASH',
        market_value: total,
        breakdown: cashBreakdown,
        orbitRadius,
        orbitSpeed: 0.0002,
        orbitAngle: angle,
        rotationSpeed: 0.001,
        planet
    };

    // Create orbit line
    const orbitPoints = [];
    for (let i = 0; i <= 64; i++) {
        const a = (i / 64) * Math.PI * 2;
        orbitPoints.push(new THREE.Vector3(
            Math.cos(a) * orbitRadius,
            0,
            Math.sin(a) * orbitRadius
        ));
    }
    const orbitGeometry = new THREE.BufferGeometry().setFromPoints(orbitPoints);
    const orbitMaterial = new THREE.LineBasicMaterial({
        color: 0xffd700,
        transparent: true,
        opacity: 0.15
    });
    const orbitLine = new THREE.Line(orbitGeometry, orbitMaterial);
    scene.add(orbitLine);

    scene.add(planetGroup);
    planets.set('CASH', { group: planetGroup, orbit: orbitLine });

    return planetGroup;
}

// Helper to create partial ring (arc)
function createPartialRing(innerRadius, outerRadius, startAngle, endAngle, color) {
    const segments = 64;
    const shape = new THREE.Shape();

    // Outer arc
    for (let i = 0; i <= segments; i++) {
        const angle = startAngle + (i / segments) * (endAngle - startAngle);
        const x = Math.cos(angle) * outerRadius;
        const y = Math.sin(angle) * outerRadius;
        if (i === 0) shape.moveTo(x, y);
        else shape.lineTo(x, y);
    }

    // Inner arc (reverse)
    for (let i = segments; i >= 0; i--) {
        const angle = startAngle + (i / segments) * (endAngle - startAngle);
        const x = Math.cos(angle) * innerRadius;
        const y = Math.sin(angle) * innerRadius;
        shape.lineTo(x, y);
    }

    shape.closePath();

    const geometry = new THREE.ShapeGeometry(shape);
    const material = new THREE.MeshBasicMaterial({
        color: color,
        transparent: true,
        opacity: 0.5,
        side: THREE.DoubleSide
    });

    return new THREE.Mesh(geometry, material);
}

function createPlanet(holding, index, total, portfolioTotal) {
    const { ticker, shares, market_value, unrealized_gain_pct, current_price } = holding;

    // Calculate size based on position size (relative to total portfolio value)
    // This makes planet sizes proportional to the sun (entire portfolio)
    const sizeRatio = market_value / portfolioTotal;
    const allocationPct = sizeRatio * 100;
    const radius = 0.8 + sizeRatio * 8; // Range: 0.8 to ~3.2 for typical allocations

    // Momentum simulation (using gain % as proxy - in real app would use price history)
    const momentum = unrealized_gain_pct / 100; // -1 to 1 roughly
    const isGain = unrealized_gain_pct >= 0;

    // ORBIT DISTANCE: Based on allocation % (larger allocation = closer to sun)
    // Inverse relationship: higher allocation = closer orbit
    // Max allocation ~40% -> orbit at 10, Min allocation ~2% -> orbit at 35
    const maxOrbit = 35;
    const minOrbit = 10;
    const orbitFromAllocation = maxOrbit - (sizeRatio * (maxOrbit - minOrbit) / 0.4);

    // Base color by ticker
    const tickerColors = {
        BMNR: 0x8B4513,  // Brown/Earth
        NBIS: 0x4169E1,  // Royal Blue
        TSLA: 0xC0C0C0,  // Silver
        META: 0x1877F2,  // Facebook Blue
        RKLB: 0x9400D3,  // Purple
        PLTR: 0x00CED1,  // Turquoise
        SPOT: 0x1DB954   // Spotify Green
    };
    const baseColor = tickerColors[ticker] || 0x888888;

    // Create planet mesh with realistic texture
    const geometry = new THREE.SphereGeometry(radius, 64, 64);
    const texture = createPlanetTexture(baseColor, isGain);
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;

    const material = new THREE.MeshStandardMaterial({
        map: texture,
        metalness: 0.1,
        roughness: 0.8,
        emissive: isGain ? 0x003311 : 0x331100,
        emissiveIntensity: 0.2 + Math.abs(momentum) * 0.3
    });

    const planet = new THREE.Mesh(geometry, material);

    // Create planet group to hold planet + effects
    const planetGroup = new THREE.Group();
    planetGroup.add(planet);

    // Add atmosphere glow (more intense for bigger gains/losses)
    const atmosphere = createAtmosphere(radius, isGain, Math.abs(momentum));
    planetGroup.add(atmosphere);

    // Add momentum particles
    const particles = createMomentumParticles(radius, momentum);
    planetGroup.add(particles);

    // Add ring for stocks with high momentum
    if (Math.abs(unrealized_gain_pct) > 20) {
        const ringGeometry = new THREE.RingGeometry(radius + 0.5, radius + 1, 64);
        const ringMaterial = new THREE.MeshBasicMaterial({
            color: isGain ? 0x00ff88 : 0xff4444,
            transparent: true,
            opacity: 0.3,
            side: THREE.DoubleSide
        });
        const ring = new THREE.Mesh(ringGeometry, ringMaterial);
        ring.rotation.x = Math.PI / 2;
        planetGroup.add(ring);
    }

    // Position in orbit around sun
    // Use allocation-based orbit distance (clamped to reasonable range)
    const orbitRadius = Math.max(minOrbit, Math.min(maxOrbit, orbitFromAllocation));
    const angle = (index / total) * Math.PI * 2;
    planetGroup.position.x = Math.cos(angle) * orbitRadius;
    planetGroup.position.z = Math.sin(angle) * orbitRadius;
    planetGroup.position.y = (Math.random() - 0.5) * 3;

    // Store data
    planetGroup.userData = {
        type: 'planet',
        ticker,
        shares,
        market_value,
        gain_pct: unrealized_gain_pct,
        allocation_pct: allocationPct,
        orbitRadius,
        orbitSpeed: 0.0003 + (1 - sizeRatio) * 0.0005, // Smaller = faster orbit
        orbitAngle: angle,
        rotationSpeed: 0.002 + Math.random() * 0.002,
        momentum,
        particles,
        planet
    };

    // Create faint orbit line
    const orbitPoints = [];
    for (let i = 0; i <= 64; i++) {
        const a = (i / 64) * Math.PI * 2;
        orbitPoints.push(new THREE.Vector3(
            Math.cos(a) * orbitRadius,
            0,
            Math.sin(a) * orbitRadius
        ));
    }
    const orbitGeometry = new THREE.BufferGeometry().setFromPoints(orbitPoints);
    const orbitMaterial = new THREE.LineBasicMaterial({
        color: 0xffffff,
        transparent: true,
        opacity: 0.1
    });
    const orbitLine = new THREE.Line(orbitGeometry, orbitMaterial);
    scene.add(orbitLine);

    scene.add(planetGroup);
    planets.set(ticker, { group: planetGroup, orbit: orbitLine });

    return planetGroup;
}

function updatePlanets(deltaTime) {
    planets.forEach((data, ticker) => {
        const group = data.group;
        const userData = group.userData;

        // Update orbit position
        userData.orbitAngle += userData.orbitSpeed;
        group.position.x = Math.cos(userData.orbitAngle) * userData.orbitRadius;
        group.position.z = Math.sin(userData.orbitAngle) * userData.orbitRadius;

        // Rotate planet on axis
        if (userData.planet) {
            userData.planet.rotation.y += userData.rotationSpeed;
        }

        // Handle Cash planet moons
        if (userData.type === 'cash-planet') {
            group.children.forEach(child => {
                if (child.userData && child.userData.type === 'cash-moon') {
                    // Orbit moon around cash planet
                    child.userData.orbitAngle += child.userData.orbitSpeed;
                    const moonOrbit = child.userData.orbitRadius;
                    child.position.x = Math.cos(child.userData.orbitAngle) * moonOrbit;
                    child.position.z = Math.sin(child.userData.orbitAngle) * moonOrbit;
                }
            });

            // Gentle golden pulse for cash planet
            const pulseIntensity = Math.sin(clock.getElapsedTime() * 1.5) * 0.1;
            if (userData.planet && userData.planet.material) {
                userData.planet.material.emissiveIntensity = 0.3 + pulseIntensity;
            }
            return;
        }

        // Animate particles
        if (userData.particles) {
            userData.particles.rotation.y += 0.005 * (1 + Math.abs(userData.momentum));
            userData.particles.rotation.x += 0.002;
        }

        // Pulse glow based on momentum
        const pulseIntensity = Math.sin(clock.getElapsedTime() * (2 + Math.abs(userData.momentum) * 3)) * 0.1;
        group.children.forEach(child => {
            if (child.material && child.material.emissiveIntensity !== undefined) {
                child.material.emissiveIntensity = 0.2 + Math.abs(userData.momentum) * 0.3 + pulseIntensity;
            }
        });
    });
}

function onWindowResize() {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
}

function animate() {
    requestAnimationFrame(animate);

    const deltaTime = clock.getDelta();

    // Update camera animation
    updateCameraAnimation(deltaTime);

    // Follow selected planet (keeps planet centered while system rotates)
    followSelectedPlanet();

    controls.update();

    // Rotate star field slowly
    if (starField) {
        starField.rotation.y += 0.00005;
    }

    // Animate sun
    if (sun) {
        sun.rotation.y += 0.001;
        const scale = 1 + Math.sin(clock.getElapsedTime() * 0.5) * 0.02;
        sun.scale.set(scale, scale, scale);
    }

    // Update planet orbits and effects
    updatePlanets(deltaTime);

    // Update popup position if a planet is selected
    if (selectedPlanet) {
        updatePopupPosition(selectedPlanet);
    }

    renderer.render(scene, camera);
}

// Fetch portfolio data
async function fetchPortfolioData() {
    try {
        const response = await fetch('/api/state');
        if (!response.ok) throw new Error('Failed to fetch');
        return await response.json();
    } catch (error) {
        console.error('Error fetching portfolio:', error);
        return null;
    }
}

// Update HUD with portfolio data
function updateHUD(data) {
    document.getElementById('total-value').textContent =
        '$' + data.total_value.toLocaleString('en-US', { maximumFractionDigits: 0 });
    document.getElementById('cash-value').textContent =
        '$' + data.cash.toLocaleString('en-US', { maximumFractionDigits: 0 });
    document.getElementById('holdings-value').textContent =
        '$' + data.portfolio_value.toLocaleString('en-US', { maximumFractionDigits: 0 });
    document.getElementById('income-value').textContent =
        '$' + data.income.total.toLocaleString('en-US', { maximumFractionDigits: 0 });
    document.getElementById('income-pct').textContent =
        data.income.progress_pct.toFixed(0) + '%';
    document.getElementById('income-progress').style.width =
        Math.min(data.income.progress_pct, 100) + '%';

    // Update holdings grid
    const grid = document.getElementById('holdings-grid');
    grid.innerHTML = '';

    // Add Cash card first with breakdown
    if (data.cash_breakdown) {
        const cb = data.cash_breakdown;
        const cashCard = document.createElement('div');
        cashCard.className = 'holding-card cash-card';
        cashCard.style.borderLeft = '3px solid #ffd700';
        cashCard.style.background = 'linear-gradient(135deg, rgba(255, 215, 0, 0.1) 0%, rgba(20, 20, 40, 0.95) 100%)';
        cashCard.innerHTML = `
            <div class="ticker" style="color: #ffd700;">CASH</div>
            <div class="value">$${cb.total.toLocaleString('en-US', { maximumFractionDigits: 0 })}</div>
            <div style="font-size: 10px; margin-top: 4px;">
                <div style="display: flex; justify-content: space-between; color: #00ff88;">
                    <span>Available:</span>
                    <span>$${cb.available.toLocaleString('en-US', { maximumFractionDigits: 0 })}</span>
                </div>
                <div style="display: flex; justify-content: space-between; color: #ff8c00;">
                    <span>Collateral:</span>
                    <span>$${cb.secured_put_collateral.toLocaleString('en-US', { maximumFractionDigits: 0 })}</span>
                </div>
                <div style="display: flex; justify-content: space-between; color: #ff4444;">
                    <span>Tax Reserve:</span>
                    <span>$${cb.tax_reserve.toLocaleString('en-US', { maximumFractionDigits: 0 })}</span>
                </div>
            </div>
        `;
        cashCard.onclick = () => focusOnPlanet('CASH');
        grid.appendChild(cashCard);
    }

    data.holdings.forEach(h => {
        const isGain = h.unrealized_gain_pct >= 0;
        const card = document.createElement('div');
        card.className = 'holding-card';
        card.style.borderLeft = `3px solid ${isGain ? '#00ff88' : '#ff4444'}`;
        card.innerHTML = `
            <div class="ticker">${h.ticker}</div>
            <div class="value">$${h.market_value.toLocaleString('en-US', { maximumFractionDigits: 0 })}</div>
            <div class="${isGain ? 'gain-positive' : 'gain-negative'}" style="font-weight: bold;">
                ${isGain ? '+' : ''}${h.unrealized_gain_pct.toFixed(1)}%
            </div>
            <div style="font-size: 11px; opacity: 0.6;">${h.shares.toLocaleString()} shares</div>
        `;

        // Focus camera on planet when clicked
        card.onclick = () => focusOnPlanet(h.ticker);
        grid.appendChild(card);
    });
}

function animateCameraTo(targetPos, lookAtPos, duration = 1.5) {
    // Stop auto-rotate during animation
    controls.autoRotate = false;

    // Set up animation
    cameraAnimation.startPos.copy(camera.position);
    cameraAnimation.endPos.copy(targetPos);
    cameraAnimation.startTarget.copy(controls.target);
    cameraAnimation.endTarget.copy(lookAtPos);
    cameraAnimation.duration = duration;
    cameraAnimation.elapsed = 0;
    cameraAnimation.active = true;
}

function updateCameraAnimation(deltaTime) {
    if (!cameraAnimation.active) return;

    cameraAnimation.elapsed += deltaTime;
    const t = Math.min(cameraAnimation.elapsed / cameraAnimation.duration, 1);
    const easedT = cameraAnimation.easing(t);

    // Interpolate camera position
    camera.position.lerpVectors(cameraAnimation.startPos, cameraAnimation.endPos, easedT);

    // Interpolate target
    controls.target.lerpVectors(cameraAnimation.startTarget, cameraAnimation.endTarget, easedT);

    if (t >= 1) {
        cameraAnimation.active = false;
        // Resume auto-rotate after 5 seconds if viewing system
        if (selectedPlanet === null) {
            setTimeout(() => { controls.autoRotate = true; }, 3000);
        }
    }
}

// Camera follow offset (stored when focusing on planet)
let cameraFollowOffset = new THREE.Vector3();

function focusOnPlanet(ticker) {
    const planetData = planets.get(ticker);
    if (!planetData) return;

    selectedPlanet = ticker;
    const group = planetData.group;

    // Calculate camera position: offset from planet
    const planetPos = group.position.clone();
    const radius = group.userData.planet?.geometry?.parameters?.radius || 2;

    // Camera offset relative to planet - store for continuous following
    cameraFollowOffset.set(radius * 3, radius * 2, radius * 3);
    const targetCameraPos = planetPos.clone().add(cameraFollowOffset);

    animateCameraTo(targetCameraPos, planetPos, 1.5);

    // Show planet info popup
    showPlanetInfo(ticker, group.position);
}

function zoomToSystem() {
    selectedPlanet = null;
    hidePlanetInfo();
    animateCameraTo(DEFAULT_CAMERA_POS, DEFAULT_TARGET, 1.5);
}

// Keep camera following the selected planet as it orbits
function followSelectedPlanet() {
    if (!selectedPlanet || cameraAnimation.active) return;

    const planetData = planets.get(selectedPlanet);
    if (!planetData) return;

    const planetPos = planetData.group.position;

    // Smoothly update camera position to follow planet
    const targetCameraPos = planetPos.clone().add(cameraFollowOffset);
    camera.position.lerp(targetCameraPos, 0.05);

    // Keep looking at the planet
    controls.target.lerp(planetPos, 0.05);
}

function onCanvasClick(event) {
    // Calculate mouse position in normalized device coordinates
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);

    // Check sun first
    if (sun) {
        const sunIntersects = raycaster.intersectObject(sun);
        if (sunIntersects.length > 0) {
            zoomToSystem();
            return;
        }
    }

    // Check planets
    const planetObjects = [];
    planets.forEach((data, ticker) => {
        if (data.group.userData.planet) {
            data.group.userData.planet.userData.ticker = ticker;
            planetObjects.push(data.group.userData.planet);
        }
    });

    const intersects = raycaster.intersectObjects(planetObjects);
    if (intersects.length > 0) {
        const ticker = intersects[0].object.userData.ticker;
        if (ticker) {
            focusOnPlanet(ticker);
        }
    }
}

function onCanvasMouseMove(event) {
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);

    // Check for hover
    const planetObjects = [];
    planets.forEach((data, ticker) => {
        if (data.group.userData.planet) {
            planetObjects.push(data.group.userData.planet);
        }
    });

    const intersects = raycaster.intersectObjects(planetObjects);

    // Update cursor
    if (intersects.length > 0 || (sun && raycaster.intersectObject(sun).length > 0)) {
        renderer.domElement.style.cursor = 'pointer';
    } else {
        renderer.domElement.style.cursor = 'default';
    }
}

function showCashPlanetInfo() {
    const cb = portfolioData?.cash_breakdown;
    if (!cb) return;

    let popup = document.getElementById('planet-info');
    if (!popup) {
        popup = document.createElement('div');
        popup.id = 'planet-info';
        popup.style.cssText = `
            position: fixed;
            background: rgba(20, 20, 40, 0.95);
            border: 2px solid #ffd700;
            border-radius: 12px;
            padding: 16px;
            pointer-events: auto;
            z-index: 1000;
            min-width: 240px;
            backdrop-filter: blur(10px);
            box-shadow: 0 4px 30px rgba(255, 215, 0, 0.3);
        `;
        document.body.appendChild(popup);
    }

    popup.style.borderColor = '#ffd700';

    popup.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <span style="font-size: 24px; font-weight: bold; color: #ffd700;">CASH</span>
            <button onclick="zoomToSystem()" style="background: none; border: 1px solid #666; color: #fff; padding: 4px 8px; border-radius: 4px; cursor: pointer;">×</button>
        </div>
        <div style="display: grid; gap: 8px;">
            <div style="display: flex; justify-content: space-between; border-bottom: 1px solid #ffd700; padding-bottom: 8px;">
                <span style="color: #ffd700; font-weight: bold;">Total Cash</span>
                <span style="font-family: monospace; font-size: 18px; color: #ffd700;">$${cb.total.toLocaleString()}</span>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="color: #00ff88;">
                    <span style="display: inline-block; width: 10px; height: 10px; background: #00ff88; border-radius: 50%; margin-right: 6px;"></span>
                    Available
                </span>
                <span style="font-family: monospace; color: #00ff88;">$${cb.available.toLocaleString()}</span>
            </div>
            <div style="font-size: 11px; color: #888; margin-left: 16px; margin-top: -4px;">
                Cash ready to deploy
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 4px;">
                <span style="color: #ff8c00;">
                    <span style="display: inline-block; width: 10px; height: 10px; background: #ff8c00; border-radius: 50%; margin-right: 6px;"></span>
                    Put Collateral
                </span>
                <span style="font-family: monospace; color: #ff8c00;">$${cb.secured_put_collateral.toLocaleString()}</span>
            </div>
            <div style="font-size: 11px; color: #888; margin-left: 16px; margin-top: -4px;">
                Backing active secured puts
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 4px;">
                <span style="color: #ff4444;">
                    <span style="display: inline-block; width: 10px; height: 10px; background: #ff4444; border-radius: 50%; margin-right: 6px;"></span>
                    Tax Reserve
                </span>
                <span style="font-family: monospace; color: #ff4444;">$${cb.tax_reserve.toLocaleString()}</span>
            </div>
            <div style="font-size: 11px; color: #888; margin-left: 16px; margin-top: -4px;">
                ${(cb.tax_rate * 100).toFixed(0)}% of $${cb.ytd_realized_gains.toLocaleString()} YTD gains
            </div>

            <div style="border-top: 1px solid #333; padding-top: 8px; margin-top: 8px;">
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: #888;">Allocated</span>
                    <span style="font-family: monospace;">${cb.allocated_pct.toFixed(1)}%</span>
                </div>
                <div style="height: 6px; background: #333; border-radius: 3px; margin-top: 6px; overflow: hidden;">
                    <div style="height: 100%; display: flex;">
                        <div style="width: ${(cb.available / cb.total * 100).toFixed(1)}%; background: #00ff88;"></div>
                        <div style="width: ${(cb.secured_put_collateral / cb.total * 100).toFixed(1)}%; background: #ff8c00;"></div>
                        <div style="width: ${(cb.tax_reserve / cb.total * 100).toFixed(1)}%; background: #ff4444;"></div>
                    </div>
                </div>
            </div>
        </div>
    `;

    popup.style.display = 'block';
    updatePopupPosition('CASH');
}

function showPlanetInfo(ticker, worldPosition) {
    // Handle CASH planet separately
    if (ticker === 'CASH') {
        showCashPlanetInfo();
        return;
    }

    // Get holding data
    const holding = portfolioData?.holdings?.find(h => h.ticker === ticker);
    if (!holding) return;

    // Create or update info popup
    let popup = document.getElementById('planet-info');
    if (!popup) {
        popup = document.createElement('div');
        popup.id = 'planet-info';
        popup.style.cssText = `
            position: fixed;
            background: rgba(20, 20, 40, 0.95);
            border: 2px solid ${holding.unrealized_gain_pct >= 0 ? '#00ff88' : '#ff4444'};
            border-radius: 12px;
            padding: 16px;
            pointer-events: auto;
            z-index: 1000;
            min-width: 200px;
            backdrop-filter: blur(10px);
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.5);
        `;
        document.body.appendChild(popup);
    }

    popup.style.borderColor = holding.unrealized_gain_pct >= 0 ? '#00ff88' : '#ff4444';

    const gainClass = holding.unrealized_gain_pct >= 0 ? 'gain-positive' : 'gain-negative';
    const gainSign = holding.unrealized_gain_pct >= 0 ? '+' : '';

    popup.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <span style="font-size: 24px; font-weight: bold;">${ticker}</span>
            <button onclick="zoomToSystem()" style="background: none; border: 1px solid #666; color: #fff; padding: 4px 8px; border-radius: 4px; cursor: pointer;">×</button>
        </div>
        <div style="display: grid; gap: 8px;">
            <div style="display: flex; justify-content: space-between;">
                <span style="color: #888;">Shares</span>
                <span style="font-family: monospace;">${holding.shares.toLocaleString()}</span>
            </div>
            <div style="display: flex; justify-content: space-between;">
                <span style="color: #888;">Price</span>
                <span style="font-family: monospace;">$${holding.current_price.toFixed(2)}</span>
            </div>
            <div style="display: flex; justify-content: space-between;">
                <span style="color: #888;">Value</span>
                <span style="font-family: monospace;">$${holding.market_value.toLocaleString()}</span>
            </div>
            <div style="display: flex; justify-content: space-between;">
                <span style="color: #888;">Cost Basis</span>
                <span style="font-family: monospace;">$${holding.cost_basis.toLocaleString()}</span>
            </div>
            <div style="display: flex; justify-content: space-between; border-top: 1px solid #333; padding-top: 8px; margin-top: 4px;">
                <span style="color: #888;">Gain/Loss</span>
                <span class="${gainClass}" style="font-weight: bold; font-size: 18px;">
                    ${gainSign}${holding.unrealized_gain_pct.toFixed(1)}%
                </span>
            </div>
            <div style="display: flex; justify-content: space-between;">
                <span style="color: #888;">Unrealized</span>
                <span class="${gainClass}" style="font-family: monospace;">
                    ${gainSign}$${Math.abs(holding.unrealized_gain).toLocaleString()}
                </span>
            </div>
            <div style="display: flex; justify-content: space-between;">
                <span style="color: #888;">Allocation</span>
                <span style="font-family: monospace;">${holding.allocation_pct.toFixed(1)}%</span>
            </div>
        </div>
    `;

    popup.style.display = 'block';

    // Position popup (will be updated in animation loop)
    updatePopupPosition(ticker);
}

function updatePopupPosition(ticker) {
    const popup = document.getElementById('planet-info');
    if (!popup || !ticker) return;

    const planetData = planets.get(ticker);
    if (!planetData) return;

    // Project 3D position to 2D screen coordinates
    const worldPos = planetData.group.position.clone();
    worldPos.project(camera);

    const x = (worldPos.x * 0.5 + 0.5) * window.innerWidth;
    const y = (-worldPos.y * 0.5 + 0.5) * window.innerHeight;

    // Position popup to the right of the planet
    popup.style.left = Math.min(x + 50, window.innerWidth - 250) + 'px';
    popup.style.top = Math.max(y - 100, 10) + 'px';
}

function hidePlanetInfo() {
    const popup = document.getElementById('planet-info');
    if (popup) {
        popup.style.display = 'none';
    }
}

// Make zoomToSystem available globally for the close button
window.zoomToSystem = zoomToSystem;

// Navigate to a path outside the /dashboard/ SPA context
function navigateTo(path) {
    // Use origin to get the base URL (e.g., http://localhost:8000)
    // This ensures we navigate to the root, not relative to /dashboard/
    window.location.href = window.location.origin + path;
}
window.navigateTo = navigateTo;

// ==================== PLAYBACK FUNCTIONALITY ====================

// Playback state
let playbackMode = false;
let playbackData = null;  // Prepared playback with daily frames
let playbackIndex = 0;
let playbackPlaying = false;
let playbackSpeed = 1;
let playbackInterval = null;
let playbackLoading = false;

async function togglePlaybackMode() {
    playbackMode = !playbackMode;
    const panel = document.getElementById('playback-panel');
    const toggleBtn = document.getElementById('playback-toggle');

    if (playbackMode) {
        // Enter playback mode
        panel.classList.add('visible');
        toggleBtn.classList.add('active');
        toggleBtn.querySelector('span').textContent = 'Exit History';

        // Load timeline data if not already loaded
        if (!playbackData && !playbackLoading) {
            await loadPlaybackTimeline();
        }
    } else {
        // Exit playback mode
        panel.classList.remove('visible');
        toggleBtn.classList.remove('active');
        toggleBtn.querySelector('span').textContent = 'History Mode';

        // Stop playback
        if (playbackPlaying) {
            togglePlayback();
        }

        // Restore current portfolio view
        if (portfolioData) {
            updateHUD(portfolioData);
            // Rebuild planets from current data
            rebuildPlanetsFromPortfolioData();
        }
    }
}
window.togglePlaybackMode = togglePlaybackMode;

function rebuildPlanetsFromPortfolioData() {
    if (!portfolioData) return;

    const totalValue = portfolioData.total_value || portfolioData.portfolio_value;

    // Animate each planet back to current state
    portfolioData.holdings.forEach((holding, index) => {
        const planetData = planets.get(holding.ticker);
        if (planetData) {
            const sizeRatio = holding.market_value / totalValue;
            const targetRadius = 0.8 + sizeRatio * 8;
            const maxOrbit = 35;
            const minOrbit = 10;
            const targetOrbit = Math.max(minOrbit, Math.min(maxOrbit, maxOrbit - (sizeRatio * (maxOrbit - minOrbit) / 0.4)));

            const group = planetData.group;
            const planet = group.userData.planet;

            if (planet) {
                const targetScale = targetRadius / (planet.geometry.parameters?.radius || 1);
                gsap.to(planet.scale, {
                    x: targetScale, y: targetScale, z: targetScale,
                    duration: PLANET_ANIMATION_DURATION,
                    ease: "power2.inOut"
                });
            }

            gsap.to(group.userData, {
                orbitRadius: targetOrbit,
                duration: PLANET_ANIMATION_DURATION,
                ease: "power2.inOut",
                onUpdate: () => {
                    group.position.x = Math.cos(group.userData.orbitAngle) * group.userData.orbitRadius;
                    group.position.z = Math.sin(group.userData.orbitAngle) * group.userData.orbitRadius;
                }
            });
        }
    });
}

async function loadPlaybackTimeline() {
    playbackLoading = true;

    // Show loading indicator
    document.getElementById('playback-event-summary').textContent = 'Loading historical prices...';
    document.getElementById('playback-event-type').textContent = 'LOADING';

    try {
        // Use the prepared-playback endpoint with real historical prices
        const response = await fetch('/api/history/prepared-playback');
        if (!response.ok) throw new Error('Failed to load timeline');

        const data = await response.json();
        playbackData = data;

        // Update slider to use frames (daily snapshots with real prices)
        const slider = document.getElementById('playback-slider');
        slider.max = data.frames.length - 1;
        slider.value = 0;

        document.getElementById('playback-progress').textContent = `1 / ${data.total_frames} days`;

        if (data.frames.length > 0) {
            playbackIndex = 0;
            updatePlaybackDisplayFromFrame(0);
        }
    } catch (error) {
        console.error('Error loading timeline:', error);
        document.getElementById('playback-event-summary').textContent = 'Error loading timeline: ' + error.message;
    } finally {
        playbackLoading = false;
    }
}

// New function to update display from pre-computed frames with real historical prices
function updatePlaybackDisplayFromFrame(index) {
    if (!playbackData || !playbackData.frames[index]) return;

    const frame = playbackData.frames[index];

    // Update event display - show if this is an event day
    if (frame.is_event_day) {
        document.getElementById('playback-event-type').textContent = frame.event_type;
        document.getElementById('playback-event-summary').textContent = frame.event_summary || frame.event_type;
    } else {
        document.getElementById('playback-event-type').textContent = 'MARKET DAY';
        document.getElementById('playback-event-summary').textContent = 'Price movement only';
    }

    document.getElementById('playback-event-timestamp').textContent = frame.timestamp;
    document.getElementById('playback-date').textContent = frame.date;
    document.getElementById('playback-progress').textContent = `${index + 1} / ${playbackData.total_frames} days`;

    // Update slider position
    document.getElementById('playback-slider').value = index;

    // Update snapshot values directly from frame (no network request needed!)
    document.getElementById('playback-cash').textContent = '$' + frame.cash.toLocaleString('en-US', { maximumFractionDigits: 0 });
    document.getElementById('playback-holdings').textContent = '$' + frame.total_holdings.toLocaleString('en-US', { maximumFractionDigits: 0 });
    document.getElementById('playback-total').textContent = '$' + frame.total_value.toLocaleString('en-US', { maximumFractionDigits: 0 });

    // Update the 3D visualization with historical prices
    updateVisualizationFromFrame(frame);
}

// Update visualization using frame data with real historical prices
function updateVisualizationFromFrame(frame) {
    // Update the HUD with frame values
    document.getElementById('total-value').textContent = '$' + frame.total_value.toLocaleString('en-US', { maximumFractionDigits: 0 });
    document.getElementById('cash-value').textContent = '$' + frame.cash.toLocaleString('en-US', { maximumFractionDigits: 0 });
    document.getElementById('holdings-value').textContent = '$' + frame.total_holdings.toLocaleString('en-US', { maximumFractionDigits: 0 });

    // Update YTD income
    document.getElementById('income-value').textContent = '$' + frame.ytd_income.toLocaleString('en-US', { maximumFractionDigits: 0 });
    const progress = (frame.ytd_income / 30000) * 100;
    document.getElementById('income-pct').textContent = progress.toFixed(0) + '%';
    document.getElementById('income-progress').style.width = Math.min(progress, 100) + '%';

    // Update holdings grid with historical holdings
    const grid = document.getElementById('holdings-grid');
    grid.innerHTML = '';

    // Add date indicator at top
    const dateCard = document.createElement('div');
    dateCard.className = 'holding-card';
    dateCard.style.borderLeft = '3px solid #888';
    dateCard.style.background = 'linear-gradient(135deg, rgba(100, 100, 100, 0.2) 0%, rgba(20, 20, 40, 0.95) 100%)';
    dateCard.innerHTML = `
        <div class="ticker" style="color: #888;">DATE</div>
        <div class="value" style="font-size: 14px;">${frame.date}</div>
        <div style="font-size: 10px; opacity: 0.6;">${frame.is_event_day ? frame.event_type : 'Market day'}</div>
    `;
    grid.appendChild(dateCard);

    for (const [ticker, data] of Object.entries(frame.holdings_value)) {
        if (data.value > 0) {
            const card = document.createElement('div');
            card.className = 'holding-card';
            card.style.borderLeft = '3px solid #888';
            card.innerHTML = `
                <div class="ticker">${ticker}</div>
                <div class="value">$${data.value.toLocaleString('en-US', { maximumFractionDigits: 0 })}</div>
                <div style="font-size: 11px; opacity: 0.6;">${data.shares.toLocaleString()} @ $${data.price.toFixed(2)}</div>
            `;
            card.onclick = () => focusOnPlanet(ticker);
            grid.appendChild(card);
        }
    }

    // Animate 3D planets to match historical state
    animatePlanetsToFrame(frame);
}

// Animate planets using frame data with real historical prices
function animatePlanetsToFrame(frame) {
    const totalValue = frame.total_value || 1;
    const holdingsValue = frame.holdings_value || {};
    const holdingsTickers = new Set(Object.keys(holdingsValue).filter(t => holdingsValue[t].value > 0));

    // Track which planets should exist
    const existingTickers = new Set(planets.keys());
    existingTickers.delete('CASH'); // Handle cash separately

    // Calculate new state for each holding
    const holdingsList = Object.entries(holdingsValue).filter(([t, d]) => d.value > 0);
    const totalHoldings = holdingsList.length;

    holdingsList.forEach(([ticker, data], index) => {
        const { value, shares, price } = data;
        const sizeRatio = value / totalValue;
        const targetRadius = 0.8 + sizeRatio * 8;

        // Calculate target orbit (closer = larger allocation)
        const maxOrbit = 35;
        const minOrbit = 10;
        const targetOrbit = Math.max(minOrbit, Math.min(maxOrbit, maxOrbit - (sizeRatio * (maxOrbit - minOrbit) / 0.4)));

        // Calculate target position angle
        const targetAngle = (index / totalHoldings) * Math.PI * 2;

        if (planets.has(ticker)) {
            // Animate existing planet
            const planetData = planets.get(ticker);
            const group = planetData.group;
            const planet = group.userData.planet;

            if (planet) {
                // Animate scale (size)
                const targetScale = targetRadius / (planet.geometry.parameters?.radius || 1);

                gsap.to(planet.scale, {
                    x: targetScale,
                    y: targetScale,
                    z: targetScale,
                    duration: PLANET_ANIMATION_DURATION,
                    ease: "power2.inOut"
                });

                // Animate atmosphere/glow children
                group.children.forEach(child => {
                    if (child !== planet && child.type === 'Group') {
                        gsap.to(child.scale, {
                            x: targetScale,
                            y: targetScale,
                            z: targetScale,
                            duration: PLANET_ANIMATION_DURATION,
                            ease: "power2.inOut"
                        });
                    }
                });
            }

            // Animate orbit radius and position
            gsap.to(group.userData, {
                orbitRadius: targetOrbit,
                duration: PLANET_ANIMATION_DURATION,
                ease: "power2.inOut",
                onUpdate: () => {
                    group.position.x = Math.cos(group.userData.orbitAngle) * group.userData.orbitRadius;
                    group.position.z = Math.sin(group.userData.orbitAngle) * group.userData.orbitRadius;
                }
            });

            // Update orbit line
            if (planetData.orbit) {
                animateOrbitLine(planetData.orbit, targetOrbit);
            }
        }
    });

    // Fade out planets that no longer exist in this frame
    existingTickers.forEach(ticker => {
        if (!holdingsTickers.has(ticker)) {
            fadeOutPlanet(ticker);
        }
    });

    // Animate cash planet based on frame cash value
    if (frame.cash > 0) {
        animateCashPlanetToValue(frame.cash, totalValue);
    }
}

function animateCashPlanetToValue(cashValue, totalValue) {
    if (!planets.has('CASH')) return;

    const planetData = planets.get('CASH');
    const group = planetData.group;

    // Calculate new size based on cash value
    const sizeRatio = cashValue / totalValue;
    const targetRadius = 0.8 + sizeRatio * 8;

    const planet = group.userData.planet;
    if (planet) {
        const targetScale = targetRadius / (planet.geometry.parameters?.radius || 1);

        gsap.to(planet.scale, {
            x: targetScale,
            y: targetScale,
            z: targetScale,
            duration: PLANET_ANIMATION_DURATION,
            ease: "power2.inOut"
        });
    }
}

// Legacy function - kept for backwards compatibility
async function updatePlaybackDisplay(index) {
    if (!playbackData) return;

    // If we have frames (new system), use frame-based display
    if (playbackData.frames && playbackData.frames[index]) {
        updatePlaybackDisplayFromFrame(index);
        return;
    }

    // Fallback to old event-based system
    if (!playbackData.events || !playbackData.events[index]) return;

    const event = playbackData.events[index];

    // Update event display
    document.getElementById('playback-event-type').textContent = event.event_type;
    document.getElementById('playback-event-summary').textContent = event.summary;
    document.getElementById('playback-event-timestamp').textContent = event.timestamp;
    document.getElementById('playback-date').textContent = event.timestamp.split(' ')[0];
    document.getElementById('playback-progress').textContent = `${index + 1} / ${playbackData.total_events} events`;

    // Update slider position
    document.getElementById('playback-slider').value = index;

    // Fetch snapshot for this event
    try {
        const response = await fetch(`/api/history/snapshot/${event.event_id}`);
        if (response.ok) {
            const snapshot = await response.json();

            // Update snapshot values
            document.getElementById('playback-cash').textContent = '$' + snapshot.cash.toLocaleString('en-US', { maximumFractionDigits: 0 });

            const holdingsValue = Object.values(snapshot.holdings_value).reduce((sum, h) => sum + h.value, 0);
            document.getElementById('playback-holdings').textContent = '$' + holdingsValue.toLocaleString('en-US', { maximumFractionDigits: 0 });
            document.getElementById('playback-total').textContent = '$' + snapshot.total_value.toLocaleString('en-US', { maximumFractionDigits: 0 });

            // Update the 3D visualization with historical data
            updateVisualizationFromSnapshot(snapshot);
        }
    } catch (error) {
        console.error('Error fetching snapshot:', error);
    }
}

function updateVisualizationFromSnapshot(snapshot) {
    // Update the HUD with snapshot values
    document.getElementById('total-value').textContent = '$' + snapshot.total_value.toLocaleString('en-US', { maximumFractionDigits: 0 });
    document.getElementById('cash-value').textContent = '$' + snapshot.cash.toLocaleString('en-US', { maximumFractionDigits: 0 });

    const holdingsValue = Object.values(snapshot.holdings_value).reduce((sum, h) => sum + h.value, 0);
    document.getElementById('holdings-value').textContent = '$' + holdingsValue.toLocaleString('en-US', { maximumFractionDigits: 0 });

    // Update YTD income
    document.getElementById('income-value').textContent = '$' + snapshot.ytd_income.toLocaleString('en-US', { maximumFractionDigits: 0 });
    const progress = (snapshot.ytd_income / 30000) * 100;
    document.getElementById('income-pct').textContent = progress.toFixed(0) + '%';
    document.getElementById('income-progress').style.width = Math.min(progress, 100) + '%';

    // Update holdings grid with historical holdings
    const grid = document.getElementById('holdings-grid');
    grid.innerHTML = '';

    for (const [ticker, data] of Object.entries(snapshot.holdings_value)) {
        const card = document.createElement('div');
        card.className = 'holding-card';
        card.style.borderLeft = '3px solid #888';
        card.innerHTML = `
            <div class="ticker">${ticker}</div>
            <div class="value">$${data.value.toLocaleString('en-US', { maximumFractionDigits: 0 })}</div>
            <div style="font-size: 11px; opacity: 0.6;">${data.shares.toLocaleString()} shares @ $${data.price.toFixed(2)}</div>
        `;
        card.onclick = () => focusOnPlanet(ticker);
        grid.appendChild(card);
    }

    // Animate 3D planets to match historical state
    animatePlanetsToSnapshot(snapshot);
}

// Animation duration in seconds
const PLANET_ANIMATION_DURATION = 0.8;

function animatePlanetsToSnapshot(snapshot) {
    const totalValue = snapshot.total_value || 1;
    const snapshotTickers = new Set(Object.keys(snapshot.holdings_value));

    // Track which planets should exist
    const existingTickers = new Set(planets.keys());
    existingTickers.delete('CASH'); // Handle cash separately

    // Calculate new state for each holding
    const holdingsList = Object.entries(snapshot.holdings_value);
    const totalHoldings = holdingsList.length;

    holdingsList.forEach(([ticker, data], index) => {
        const { value, shares, price, cost_basis } = data;
        const sizeRatio = value / totalValue;
        const targetRadius = 0.8 + sizeRatio * 8;

        // Calculate gain/loss for coloring
        const totalCost = cost_basis || (shares * price);
        const gainPct = totalCost > 0 ? ((value - totalCost) / totalCost) * 100 : 0;
        const isGain = gainPct >= 0;

        // Calculate target orbit (closer = larger allocation)
        const maxOrbit = 35;
        const minOrbit = 10;
        const targetOrbit = Math.max(minOrbit, Math.min(maxOrbit, maxOrbit - (sizeRatio * (maxOrbit - minOrbit) / 0.4)));

        // Calculate target position angle
        const targetAngle = (index / totalHoldings) * Math.PI * 2;

        if (planets.has(ticker)) {
            // Animate existing planet
            const planetData = planets.get(ticker);
            const group = planetData.group;
            const planet = group.userData.planet;

            if (planet) {
                // Animate scale (size)
                const currentScale = planet.scale.x;
                const targetScale = targetRadius / (planet.geometry.parameters?.radius || 1);

                gsap.to(planet.scale, {
                    x: targetScale,
                    y: targetScale,
                    z: targetScale,
                    duration: PLANET_ANIMATION_DURATION,
                    ease: "power2.inOut"
                });

                // Animate atmosphere/glow children
                group.children.forEach(child => {
                    if (child !== planet && child.type === 'Group') {
                        gsap.to(child.scale, {
                            x: targetScale,
                            y: targetScale,
                            z: targetScale,
                            duration: PLANET_ANIMATION_DURATION,
                            ease: "power2.inOut"
                        });
                    }
                });
            }

            // Animate orbit radius and position
            const currentOrbit = group.userData.orbitRadius;
            const startAngle = group.userData.orbitAngle || 0;

            gsap.to(group.userData, {
                orbitRadius: targetOrbit,
                duration: PLANET_ANIMATION_DURATION,
                ease: "power2.inOut",
                onUpdate: () => {
                    // Update position based on current orbit radius and angle
                    group.position.x = Math.cos(group.userData.orbitAngle) * group.userData.orbitRadius;
                    group.position.z = Math.sin(group.userData.orbitAngle) * group.userData.orbitRadius;
                }
            });

            // Update orbit line
            if (planetData.orbit) {
                animateOrbitLine(planetData.orbit, targetOrbit);
            }

            // Update glow color based on gain/loss
            updatePlanetGlow(group, isGain, Math.abs(gainPct) / 100);

        } else {
            // Create new planet with fade-in animation
            createAnimatedPlanet(ticker, data, index, totalHoldings, totalValue);
        }
    });

    // Fade out and remove planets that no longer exist
    existingTickers.forEach(ticker => {
        if (!snapshotTickers.has(ticker)) {
            fadeOutPlanet(ticker);
        }
    });

    // Animate cash planet
    if (snapshot.cash_breakdown) {
        animateCashPlanet(snapshot.cash_breakdown, totalValue);
    }
}

function animateOrbitLine(orbitLine, targetRadius) {
    const positions = orbitLine.geometry.attributes.position;
    const segments = positions.count - 1;
    const startRadius = Math.sqrt(positions.array[0] ** 2 + positions.array[2] ** 2);

    gsap.to({ radius: startRadius }, {
        radius: targetRadius,
        duration: PLANET_ANIMATION_DURATION,
        ease: "power2.inOut",
        onUpdate: function() {
            const currentRadius = this.targets()[0].radius;
            for (let i = 0; i <= segments; i++) {
                const theta = (i / segments) * Math.PI * 2;
                positions.array[i * 3] = Math.cos(theta) * currentRadius;
                positions.array[i * 3 + 2] = Math.sin(theta) * currentRadius;
            }
            positions.needsUpdate = true;
        }
    });
}

function updatePlanetGlow(group, isGain, intensity) {
    const glowColor = isGain ? 0x00ff88 : 0xff4444;

    group.children.forEach(child => {
        if (child.type === 'Group') {
            // This is the atmosphere group
            child.children.forEach(glowMesh => {
                if (glowMesh.material && glowMesh.material.color) {
                    gsap.to(glowMesh.material.color, {
                        r: ((glowColor >> 16) & 255) / 255,
                        g: ((glowColor >> 8) & 255) / 255,
                        b: (glowColor & 255) / 255,
                        duration: PLANET_ANIMATION_DURATION
                    });
                    gsap.to(glowMesh.material, {
                        opacity: 0.2 + intensity * 0.3,
                        duration: PLANET_ANIMATION_DURATION
                    });
                }
            });
        }
    });
}

function createAnimatedPlanet(ticker, data, index, total, portfolioTotal) {
    const { value, shares, price, cost_basis } = data;

    // Create a minimal holding object for createPlanet
    const holding = {
        ticker: ticker,
        shares: shares,
        market_value: value,
        current_price: price,
        unrealized_gain_pct: cost_basis ? ((value - cost_basis) / cost_basis) * 100 : 0
    };

    // Create planet (it will be added to scene)
    const planetGroup = createPlanet(holding, index, total, portfolioTotal);

    // Start with scale 0 and fade in
    planetGroup.scale.set(0.01, 0.01, 0.01);
    planetGroup.traverse(child => {
        if (child.material) {
            child.material.transparent = true;
            child.material.opacity = 0;
        }
    });

    // Animate scale and opacity
    gsap.to(planetGroup.scale, {
        x: 1, y: 1, z: 1,
        duration: PLANET_ANIMATION_DURATION,
        ease: "back.out(1.7)"
    });

    planetGroup.traverse(child => {
        if (child.material) {
            gsap.to(child.material, {
                opacity: child.material.userData?.originalOpacity || 1,
                duration: PLANET_ANIMATION_DURATION
            });
        }
    });
}

function fadeOutPlanet(ticker) {
    const planetData = planets.get(ticker);
    if (!planetData) return;

    const group = planetData.group;
    const orbit = planetData.orbit;

    // Animate scale to 0 and fade out
    gsap.to(group.scale, {
        x: 0.01, y: 0.01, z: 0.01,
        duration: PLANET_ANIMATION_DURATION,
        ease: "back.in(1.7)",
        onComplete: () => {
            // Remove from scene
            scene.remove(group);
            if (orbit) scene.remove(orbit);
            planets.delete(ticker);

            // Dispose geometries and materials
            group.traverse(child => {
                if (child.geometry) child.geometry.dispose();
                if (child.material) {
                    if (Array.isArray(child.material)) {
                        child.material.forEach(m => m.dispose());
                    } else {
                        child.material.dispose();
                    }
                }
            });
        }
    });

    // Fade out orbit line
    if (orbit && orbit.material) {
        gsap.to(orbit.material, {
            opacity: 0,
            duration: PLANET_ANIMATION_DURATION
        });
    }
}

function animateCashPlanet(cashBreakdown, totalValue) {
    if (!planets.has('CASH')) return;

    const planetData = planets.get('CASH');
    const group = planetData.group;

    // Calculate new size based on cash value
    const totalCash = cashBreakdown.total || 0;
    const sizeRatio = totalCash / totalValue;
    const targetRadius = 0.8 + sizeRatio * 8;

    const planet = group.userData.planet;
    if (planet) {
        const targetScale = targetRadius / (planet.geometry.parameters?.radius || 1);

        gsap.to(planet.scale, {
            x: targetScale,
            y: targetScale,
            z: targetScale,
            duration: PLANET_ANIMATION_DURATION,
            ease: "power2.inOut"
        });
    }

    // Update orbit position (cash stays at fixed orbit distance 8)
    const targetOrbit = 8;
    gsap.to(group.userData, {
        orbitRadius: targetOrbit,
        duration: PLANET_ANIMATION_DURATION,
        ease: "power2.inOut",
        onUpdate: () => {
            group.position.x = Math.cos(group.userData.orbitAngle) * group.userData.orbitRadius;
            group.position.z = Math.sin(group.userData.orbitAngle) * group.userData.orbitRadius;
        }
    });
}

function togglePlayback() {
    playbackPlaying = !playbackPlaying;
    const btn = document.getElementById('playback-play-btn');

    if (playbackPlaying) {
        btn.innerHTML = '||';
        startPlaybackAnimation();
    } else {
        btn.innerHTML = '|>';
        stopPlaybackAnimation();
    }
}
window.togglePlayback = togglePlayback;

function startPlaybackAnimation() {
    const intervalMs = 1500 / playbackSpeed;  // Base: 1.5 seconds per day (faster for daily frames)

    // Determine max index based on data type
    const maxIndex = playbackData.frames ? playbackData.frames.length - 1 : playbackData.events.length - 1;

    playbackInterval = setInterval(() => {
        if (playbackIndex < maxIndex) {
            playbackIndex++;
            // Use frame-based or event-based display depending on data
            if (playbackData.frames) {
                updatePlaybackDisplayFromFrame(playbackIndex);
            } else {
                updatePlaybackDisplay(playbackIndex);
            }
        } else {
            // Reached end
            togglePlayback();
        }
    }, intervalMs);
}

function stopPlaybackAnimation() {
    if (playbackInterval) {
        clearInterval(playbackInterval);
        playbackInterval = null;
    }
}

function setPlaybackSpeed(speed) {
    playbackSpeed = speed;

    // Update button states
    document.querySelectorAll('.speed-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.textContent === speed + 'x') {
            btn.classList.add('active');
        }
    });

    // Restart animation with new speed if playing
    if (playbackPlaying) {
        stopPlaybackAnimation();
        startPlaybackAnimation();
    }
}
window.setPlaybackSpeed = setPlaybackSpeed;

function playbackStep(direction) {
    const maxIndex = playbackData.frames ? playbackData.frames.length - 1 : playbackData.events.length - 1;
    const newIndex = playbackIndex + direction;
    if (newIndex >= 0 && newIndex <= maxIndex) {
        playbackIndex = newIndex;
        if (playbackData.frames) {
            updatePlaybackDisplayFromFrame(playbackIndex);
        } else {
            updatePlaybackDisplay(playbackIndex);
        }
    }
}
window.playbackStep = playbackStep;

function onSliderChange(value) {
    playbackIndex = parseInt(value);
    if (playbackData.frames) {
        updatePlaybackDisplayFromFrame(playbackIndex);
    } else {
        updatePlaybackDisplay(playbackIndex);
    }
}
window.onSliderChange = onSliderChange;

// ==================== LEGEND FUNCTIONALITY ====================

function toggleLegend() {
    const panel = document.getElementById('legend-panel');
    const icon = document.getElementById('legend-toggle-icon');
    const isMinimized = panel.classList.contains('minimized');

    if (isMinimized) {
        panel.classList.remove('minimized');
        icon.textContent = '−';
    } else {
        panel.classList.add('minimized');
        icon.textContent = '+';
    }
}
window.toggleLegend = toggleLegend;

// ==================== AI INSIGHTS FUNCTIONALITY ====================

let insightsMinimized = false;

function toggleInsights() {
    const panel = document.getElementById('insights-panel');
    const icon = document.getElementById('insights-toggle-icon');
    insightsMinimized = !insightsMinimized;

    if (insightsMinimized) {
        panel.classList.add('minimized');
        icon.textContent = '+';
    } else {
        panel.classList.remove('minimized');
        icon.textContent = '−';
    }
}
window.toggleInsights = toggleInsights;

async function fetchInsights() {
    const loadingEl = document.getElementById('insights-loading');
    const listEl = document.getElementById('insights-list');
    const timestampEl = document.getElementById('insights-timestamp');
    const panel = document.getElementById('insights-panel');

    // Show loading state
    loadingEl.style.display = 'flex';
    listEl.style.display = 'none';
    panel.classList.add('loading');

    try {
        const response = await fetch('/api/research/insights');
        if (!response.ok) throw new Error('Failed to fetch insights');

        const data = await response.json();

        // Build HTML for insights
        let html = '';

        // Dexter analysis if available
        if (data.dexter_analysis) {
            html += `
                <div class="dexter-analysis">
                    <div class="dexter-header">
                        <span class="dexter-badge">Dexter</span>
                        <span class="dexter-ticker">${data.dexter_analysis.ticker} Analysis</span>
                    </div>
                    <div class="dexter-text">${escapeHtml(data.dexter_analysis.analysis)}</div>
                </div>
            `;
        }

        // Regular insights
        if (data.insights && data.insights.length > 0) {
            for (const insight of data.insights) {
                const type = insight.type || 'info';
                const icon = type === 'risk' ? '⚠' : type === 'opportunity' ? '✦' : 'ℹ';

                html += `
                    <div class="insight-card ${type}">
                        <div class="insight-header">
                            <div class="insight-icon">${icon}</div>
                            <div class="insight-title">${escapeHtml(insight.title)}</div>
                        </div>
                        <div class="insight-text">${escapeHtml(insight.insight)}</div>
                    </div>
                `;
            }
        } else {
            html = '<div class="insight-card info"><div class="insight-text">No insights available. Add some holdings to get started!</div></div>';
        }

        listEl.innerHTML = html;

        // Update timestamp
        const now = new Date();
        timestampEl.textContent = `Updated ${now.toLocaleTimeString()}`;

    } catch (error) {
        console.error('Error fetching insights:', error);
        listEl.innerHTML = `
            <div class="insight-card risk">
                <div class="insight-header">
                    <div class="insight-icon">⚠</div>
                    <div class="insight-title">Error Loading Insights</div>
                </div>
                <div class="insight-text">Could not fetch AI insights. Check LLM configuration.</div>
            </div>
        `;
        timestampEl.textContent = 'Failed to load';
    } finally {
        // Hide loading, show content
        loadingEl.style.display = 'none';
        listEl.style.display = 'block';
        panel.classList.remove('loading');
    }
}

function refreshInsights() {
    fetchInsights();
}
window.refreshInsights = refreshInsights;

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==================== CHAT FUNCTIONALITY ====================

// Store conversation history (persists until page close)
let conversationHistory = [];

function toggleChat() {
    const panel = document.getElementById('chat-panel');
    const icon = document.getElementById('chat-toggle-icon');
    const isMinimized = panel.classList.contains('minimized');

    if (isMinimized) {
        panel.classList.remove('minimized');
        icon.textContent = '−';
        document.getElementById('chat-input').focus();
    } else {
        panel.classList.add('minimized');
        icon.textContent = '+';
    }
}
window.toggleChat = toggleChat;

function handleChatKeypress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendChatMessage();
    }
}
window.handleChatKeypress = handleChatKeypress;

async function sendChatMessage() {
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('chat-send');
    const messagesContainer = document.getElementById('chat-messages');

    const message = input.value.trim();
    if (!message) return;

    // Clear input and disable send
    input.value = '';
    sendBtn.disabled = true;

    // Add user message to UI
    const userMsgEl = document.createElement('div');
    userMsgEl.className = 'chat-message user';
    userMsgEl.textContent = message;
    messagesContainer.appendChild(userMsgEl);

    // Add loading indicator
    const loadingEl = document.createElement('div');
    loadingEl.className = 'chat-message assistant loading';
    loadingEl.textContent = 'Thinking...';
    messagesContainer.appendChild(loadingEl);

    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    try {
        const response = await fetch('/api/chat/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                conversation_history: conversationHistory,
                include_portfolio_history: true
            })
        });

        const data = await response.json();

        // Remove loading indicator
        loadingEl.remove();

        if (response.ok) {
            // Add to conversation history
            conversationHistory.push({ role: 'user', content: message });
            conversationHistory.push({ role: 'assistant', content: data.response });

            // Keep history reasonable (last 20 messages)
            if (conversationHistory.length > 20) {
                conversationHistory = conversationHistory.slice(-20);
            }

            // Add assistant response to UI
            const assistantMsgEl = document.createElement('div');
            assistantMsgEl.className = 'chat-message assistant';
            assistantMsgEl.textContent = data.response;
            messagesContainer.appendChild(assistantMsgEl);
        } else {
            // Show error
            const errorMsgEl = document.createElement('div');
            errorMsgEl.className = 'chat-message assistant';
            errorMsgEl.style.color = '#ff6b6b';
            errorMsgEl.textContent = `Error: ${data.detail || 'Failed to get response'}`;
            messagesContainer.appendChild(errorMsgEl);
        }
    } catch (error) {
        loadingEl.remove();
        const errorMsgEl = document.createElement('div');
        errorMsgEl.className = 'chat-message assistant';
        errorMsgEl.style.color = '#ff6b6b';
        errorMsgEl.textContent = `Error: ${error.message}`;
        messagesContainer.appendChild(errorMsgEl);
    }

    // Re-enable send and scroll
    sendBtn.disabled = false;
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}
window.sendChatMessage = sendChatMessage;

// ==================== LLM SETTINGS ====================

function toggleSettings() {
    const panel = document.getElementById('settings-panel');
    const isVisible = panel.classList.contains('visible');

    if (isVisible) {
        panel.classList.remove('visible');
    } else {
        panel.classList.add('visible');
        loadLLMSettings();
    }
}
window.toggleSettings = toggleSettings;

function onProviderChange() {
    const provider = document.getElementById('llm-provider').value;
    const apiKeyGroup = document.getElementById('api-key-group');
    const claudeGroup = document.getElementById('claude-model-group');
    const localUrlGroup = document.getElementById('local-url-group');
    const localModelGroup = document.getElementById('local-model-group');

    if (provider === 'claude') {
        apiKeyGroup.style.display = 'block';
        claudeGroup.style.display = 'block';
        localUrlGroup.style.display = 'none';
        localModelGroup.style.display = 'none';
    } else {
        apiKeyGroup.style.display = 'none';
        claudeGroup.style.display = 'none';
        localUrlGroup.style.display = 'block';
        localModelGroup.style.display = 'block';
    }
}
window.onProviderChange = onProviderChange;

async function loadLLMSettings() {
    try {
        const response = await fetch('/api/config/llm');
        const data = await response.json();

        document.getElementById('llm-provider').value = data.provider;
        document.getElementById('claude-model').value = data.claude_model;
        document.getElementById('local-url').value = data.local_url;
        document.getElementById('local-model').value = data.local_model;

        // Show API key status
        updateApiKeyStatus(data.has_api_key);

        onProviderChange();

        // Also refresh the status indicator
        refreshLLMStatus();
    } catch (error) {
        showSettingsStatus('Failed to load settings: ' + error.message, 'error');
    }
}

async function refreshLLMStatus() {
    const indicator = document.getElementById('llm-indicator');
    const providerEl = document.getElementById('llm-status-provider');
    const modelEl = document.getElementById('llm-status-model');
    const latencyEl = document.getElementById('llm-status-latency');
    const latencyBar = document.getElementById('llm-latency-bar');
    const statusText = document.getElementById('llm-status-text');
    const messageEl = document.getElementById('llm-status-message');

    // Set checking state
    indicator.className = 'llm-status-indicator checking';
    statusText.textContent = 'Checking...';
    statusText.className = 'llm-status-value';
    messageEl.textContent = 'Establishing neural link...';
    messageEl.className = 'llm-status-message';

    try {
        const response = await fetch('/api/config/llm/status');
        const status = await response.json();

        // Update provider and model
        providerEl.textContent = status.provider === 'claude' ? 'Claude' : 'Local';
        modelEl.textContent = status.model || '--';

        if (status.connected) {
            indicator.className = 'llm-status-indicator connected';
            statusText.textContent = 'Online';
            statusText.className = 'llm-status-value highlight';
            messageEl.textContent = 'Neural link established';
            messageEl.className = 'llm-status-message connected';

            // Show latency
            if (status.latency_ms) {
                latencyEl.textContent = status.latency_ms + 'ms';
                // Scale latency bar (0-2000ms range)
                const pct = Math.min(100, (status.latency_ms / 2000) * 100);
                latencyBar.style.width = pct + '%';
            }
        } else {
            indicator.className = 'llm-status-indicator disconnected';
            statusText.textContent = 'Offline';
            statusText.className = 'llm-status-value error';
            latencyEl.textContent = '--';
            latencyBar.style.width = '0%';

            if (status.error) {
                messageEl.textContent = status.error;
                messageEl.className = 'llm-status-message';
            } else {
                messageEl.textContent = 'Connection failed';
                messageEl.className = 'llm-status-message';
            }
        }
    } catch (error) {
        indicator.className = 'llm-status-indicator disconnected';
        statusText.textContent = 'Error';
        statusText.className = 'llm-status-value error';
        messageEl.textContent = error.message;
        messageEl.className = 'llm-status-message';
    }
}
window.refreshLLMStatus = refreshLLMStatus;

async function saveLLMSettings() {
    const provider = document.getElementById('llm-provider').value;
    const claudeModel = document.getElementById('claude-model').value;
    const localUrl = document.getElementById('local-url').value;
    const localModel = document.getElementById('local-model').value;
    const apiKey = document.getElementById('api-key').value;

    const payload = {
        provider: provider,
        claude_model: claudeModel,
        local_url: localUrl,
        local_model: localModel
    };

    // Only include API key if it was entered (not empty)
    if (apiKey && apiKey.trim()) {
        payload.api_key = apiKey.trim();
    }

    try {
        const response = await fetch('/api/config/llm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            const data = await response.json();
            // Clear the API key field after saving
            document.getElementById('api-key').value = '';
            updateApiKeyStatus(data.has_api_key);
            showSettingsStatus('Settings saved successfully!', 'success');
            // Refresh status indicator after saving
            setTimeout(() => refreshLLMStatus(), 500);
        } else {
            const data = await response.json();
            showSettingsStatus('Failed: ' + (data.detail || 'Unknown error'), 'error');
        }
    } catch (error) {
        showSettingsStatus('Failed to save: ' + error.message, 'error');
    }
}
window.saveLLMSettings = saveLLMSettings;

function updateApiKeyStatus(hasKey) {
    const statusEl = document.getElementById('api-key-status');
    if (hasKey) {
        statusEl.innerHTML = '<span style="color: #00ff88;">✓ API key configured</span>';
    } else {
        statusEl.innerHTML = '<span style="color: #ff4444;">✗ No API key set</span>';
    }
}

async function testLLM() {
    showSettingsStatus('Testing connection...', '');

    try {
        const response = await fetch('/api/config/llm/test', { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            showSettingsStatus(`Connected to ${data.provider} (${data.model}): "${data.response}"`, 'success');
        } else {
            showSettingsStatus('Test failed: ' + data.error, 'error');
        }
    } catch (error) {
        showSettingsStatus('Test failed: ' + error.message, 'error');
    }
}
window.testLLM = testLLM;

function showSettingsStatus(message, type) {
    const status = document.getElementById('settings-status');
    status.textContent = message;
    status.className = 'settings-status' + (type ? ' ' + type : '');
    status.style.display = message ? 'block' : 'none';

    // Auto-hide success messages
    if (type === 'success') {
        setTimeout(() => {
            status.style.display = 'none';
        }, 3000);
    }
}

// Update prices
async function refreshPrices() {
    try {
        const response = await fetch('/api/prices/update', { method: 'POST' });
        if (response.ok) {
            location.reload(); // Reload to get new data
        }
    } catch (error) {
        console.error('Error updating prices:', error);
    }
}

// Make refreshPrices available globally
window.refreshPrices = refreshPrices;

// ==================== SETUP FUNCTIONALITY ====================

async function checkSetupStatus() {
    try {
        const response = await fetch('/api/setup/status');
        if (!response.ok) throw new Error('Failed to check status');
        return await response.json();
    } catch (error) {
        console.error('Error checking setup status:', error);
        return { needs_setup: true, mode: 'none' };
    }
}

async function checkDemoMode() {
    try {
        const response = await fetch('/api/setup/is-demo');
        if (!response.ok) return false;
        const data = await response.json();
        return data.is_demo;
    } catch (error) {
        return false;
    }
}

function showSetupScreen() {
    document.getElementById('setup-screen').classList.remove('hidden');
    document.getElementById('loading').style.display = 'none';
}

function hideSetupScreen() {
    document.getElementById('setup-screen').classList.add('hidden');
}

function showSetupLoading(message) {
    document.querySelector('.setup-options').style.display = 'none';
    document.getElementById('fresh-setup-form').style.display = 'none';
    document.getElementById('upload-setup-form').style.display = 'none';
    document.getElementById('setup-loading').style.display = 'block';
    document.getElementById('setup-loading-text').textContent = message;
}

function hideSetupForms() {
    document.querySelector('.setup-options').style.display = 'flex';
    document.getElementById('fresh-setup-form').style.display = 'none';
    document.getElementById('upload-setup-form').style.display = 'none';
}

function showFreshSetup() {
    document.querySelector('.setup-options').style.display = 'none';
    document.getElementById('fresh-setup-form').style.display = 'block';
}
window.showFreshSetup = showFreshSetup;

function showUploadSetup() {
    document.querySelector('.setup-options').style.display = 'none';
    document.getElementById('upload-setup-form').style.display = 'block';
}
window.showUploadSetup = showUploadSetup;

window.hideSetupForms = hideSetupForms;

async function initDemo() {
    showSetupLoading('Generating 6 months of demo data...');

    try {
        const response = await fetch('/api/setup/init-demo', { method: 'POST' });
        const data = await response.json();

        if (response.ok && data.success) {
            // Reload page to load demo data
            window.location.reload();
        } else {
            alert('Failed to initialize demo: ' + (data.detail || 'Unknown error'));
            hideSetupForms();
        }
    } catch (error) {
        alert('Failed to initialize demo: ' + error.message);
        hideSetupForms();
    }
}
window.initDemo = initDemo;

async function initFresh() {
    const startingCash = parseFloat(document.getElementById('starting-cash').value) || 50000;
    showSetupLoading('Creating your portfolio...');

    try {
        const response = await fetch('/api/setup/init-fresh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: 'fresh', starting_cash: startingCash })
        });
        const data = await response.json();

        if (response.ok && data.success) {
            window.location.reload();
        } else {
            alert('Failed to create portfolio: ' + (data.detail || 'Unknown error'));
            hideSetupForms();
        }
    } catch (error) {
        alert('Failed to create portfolio: ' + error.message);
        hideSetupForms();
    }
}
window.initFresh = initFresh;

async function uploadCSV() {
    const fileInput = document.getElementById('csv-upload');
    if (!fileInput.files.length) {
        alert('Please select a CSV file');
        return;
    }

    showSetupLoading('Importing your data...');

    try {
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);

        const response = await fetch('/api/setup/upload-csv', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();

        if (response.ok && data.success) {
            window.location.reload();
        } else {
            alert('Failed to import: ' + (data.detail || 'Unknown error'));
            hideSetupForms();
        }
    } catch (error) {
        alert('Failed to import: ' + error.message);
        hideSetupForms();
    }
}
window.uploadCSV = uploadCSV;

async function exitDemoMode() {
    if (!confirm('This will clear all demo data. Continue?')) return;

    try {
        const response = await fetch('/api/setup/exit-demo', { method: 'POST' });
        if (response.ok) {
            window.location.reload();
        }
    } catch (error) {
        alert('Failed to exit demo: ' + error.message);
    }
}
window.exitDemoMode = exitDemoMode;

function startFresh() {
    exitDemoMode().then(() => {
        // Will reload and show setup screen
    });
}
window.startFresh = startFresh;

function showDemoBanner() {
    isDemoMode = true;
    document.getElementById('demo-banner').classList.add('visible');
    document.body.classList.add('demo-mode');
}

function hideDemoBanner() {
    isDemoMode = false;
    document.getElementById('demo-banner').classList.remove('visible');
    document.body.classList.remove('demo-mode');
}

// Main initialization
async function main() {
    // Check setup status first
    const status = await checkSetupStatus();

    if (status.needs_setup || status.mode === 'none') {
        // No data exists - show setup screen
        showSetupScreen();
        return;
    }

    // Check if we're in demo mode
    const isDemo = await checkDemoMode();
    if (isDemo) {
        showDemoBanner();
    }

    // Initialize Three.js scene
    init();

    // Fetch portfolio data
    portfolioData = await fetchPortfolioData();

    if (portfolioData) {
        // Hide loading, show HUD
        document.getElementById('loading').style.display = 'none';
        document.getElementById('hud').style.display = 'block';

        // Update HUD
        updateHUD(portfolioData);

        // Use total portfolio value for relative sizing (planets relative to the sun/total)
        const totalValue = portfolioData.total_value || portfolioData.portfolio_value;

        // Create Cash planet first (if cash breakdown available)
        if (portfolioData.cash_breakdown) {
            createCashPlanet(portfolioData.cash_breakdown, totalValue);
        }

        // Create planets for each holding
        portfolioData.holdings.forEach((holding, index) => {
            createPlanet(holding, index, portfolioData.holdings.length, totalValue);
        });

        // Fetch AI insights in background (non-blocking)
        fetchInsights();
    } else {
        document.getElementById('loading').innerHTML = `
            <p style="color: #ff4444;">Failed to load portfolio data.</p>
            <p>Make sure the API server is running at localhost:8000</p>
            <button onclick="location.reload()" class="btn" style="margin-top: 16px; pointer-events: auto;">Retry</button>
        `;
    }
}

// Start
main();
