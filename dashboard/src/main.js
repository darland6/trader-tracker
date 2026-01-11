import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import gsap from 'gsap';

// Global state
let scene, camera, renderer, controls;
let planets = new Map();
let sun, starField;
let portfolioData = null;
let clock = new THREE.Clock();
let isDemoMode = false;

// Cluster view state
let clusterViewActive = false;
let clusterSystems = [];  // Array of {id, name, group, projection, frames}
let clusterTimelinePosition = 0;  // 0-1 normalized timeline position
let clusterMaxMonths = 36;  // Default 3 years
let mainSystemGroup = null;  // Group containing the main solar system for hiding

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

// Alternate Reality Pyramid - Ethereum-style mysterious object
let alternateRealityPyramid = null;
let altHistoryData = { histories: [], selectedId: null, compareId: null };

function createAlternateRealityPyramid() {
    // Create Ethereum-style pyramid (octahedron - diamond shape)
    const geometry = new THREE.OctahedronGeometry(2, 0);

    // Ethereal purple/blue material with glow
    const material = new THREE.MeshStandardMaterial({
        color: 0x627eea,  // Ethereum blue
        metalness: 0.9,
        roughness: 0.1,
        emissive: 0x3d5afe,
        emissiveIntensity: 0.5,
        transparent: true,
        opacity: 0.85
    });

    const pyramid = new THREE.Mesh(geometry, material);

    // Create group to hold pyramid and effects
    const pyramidGroup = new THREE.Group();
    pyramidGroup.add(pyramid);

    // Add ethereal glow layers
    for (let i = 1; i <= 3; i++) {
        const glowGeometry = new THREE.OctahedronGeometry(2 + i * 0.3, 0);
        const glowMaterial = new THREE.MeshBasicMaterial({
            color: 0x627eea,
            transparent: true,
            opacity: 0.1 / i,
            side: THREE.BackSide,
            wireframe: i === 3
        });
        const glow = new THREE.Mesh(glowGeometry, glowMaterial);
        pyramidGroup.add(glow);
    }

    // Add orbiting particles (mystical effect)
    const particleCount = 100;
    const particleGeometry = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);

    for (let i = 0; i < particleCount; i++) {
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.random() * Math.PI;
        const r = 2.5 + Math.random() * 1.5;

        positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
        positions[i * 3 + 1] = r * Math.cos(phi);
        positions[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta);

        // Purple/blue colors
        colors[i * 3] = 0.4 + Math.random() * 0.3;
        colors[i * 3 + 1] = 0.5 + Math.random() * 0.3;
        colors[i * 3 + 2] = 0.9 + Math.random() * 0.1;
    }

    particleGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    particleGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const particleMaterial = new THREE.PointsMaterial({
        size: 0.08,
        vertexColors: true,
        transparent: true,
        opacity: 0.8,
        blending: THREE.AdditiveBlending
    });

    const particles = new THREE.Points(particleGeometry, particleMaterial);
    pyramidGroup.add(particles);

    // Add inner wireframe for extra effect
    const wireGeometry = new THREE.OctahedronGeometry(1.5, 0);
    const wireMaterial = new THREE.MeshBasicMaterial({
        color: 0xffffff,
        wireframe: true,
        transparent: true,
        opacity: 0.3
    });
    const wireframe = new THREE.Mesh(wireGeometry, wireMaterial);
    pyramidGroup.add(wireframe);

    // Position far out in the system - mysterious distant object
    const orbitRadius = 45;
    const angle = Math.PI * 1.5; // Position it away from main planets
    pyramidGroup.position.x = Math.cos(angle) * orbitRadius;
    pyramidGroup.position.z = Math.sin(angle) * orbitRadius;
    pyramidGroup.position.y = 8; // Float above the orbital plane

    // Store data
    pyramidGroup.userData = {
        type: 'alternate-reality',
        name: 'Alternate Realities',
        orbitRadius,
        orbitAngle: angle,
        orbitSpeed: 0.00005, // Very slow orbit
        rotationSpeed: 0.005,
        pyramid,
        particles,
        wireframe
    };

    scene.add(pyramidGroup);
    alternateRealityPyramid = pyramidGroup;
    planets.set('ALT_REALITY', { group: pyramidGroup, orbit: null });

    return pyramidGroup;
}

// Update pyramid animation
function updateAlternateRealityPyramid(deltaTime) {
    if (!alternateRealityPyramid) return;

    const userData = alternateRealityPyramid.userData;

    // Slow orbit
    userData.orbitAngle += userData.orbitSpeed;
    alternateRealityPyramid.position.x = Math.cos(userData.orbitAngle) * userData.orbitRadius;
    alternateRealityPyramid.position.z = Math.sin(userData.orbitAngle) * userData.orbitRadius;

    // Gentle floating motion
    alternateRealityPyramid.position.y = 8 + Math.sin(Date.now() * 0.001) * 0.5;

    // Rotate pyramid
    if (userData.pyramid) {
        userData.pyramid.rotation.y += userData.rotationSpeed;
        userData.pyramid.rotation.x = Math.sin(Date.now() * 0.0005) * 0.1;
    }

    // Counter-rotate wireframe
    if (userData.wireframe) {
        userData.wireframe.rotation.y -= userData.rotationSpeed * 0.5;
        userData.wireframe.rotation.z += userData.rotationSpeed * 0.3;
    }

    // Rotate particles
    if (userData.particles) {
        userData.particles.rotation.y += userData.rotationSpeed * 0.2;
    }
}

// Show Alternate Reality Modal
function showAlternateRealityModal() {
    // Create modal if it doesn't exist
    let modal = document.getElementById('alt-reality-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'alt-reality-modal';
        modal.innerHTML = `
            <div class="alt-modal-backdrop" onclick="closeAltRealityModal()"></div>
            <div class="alt-modal-content">
                <div class="alt-modal-header">
                    <h2>Alternate Realities</h2>
                    <div class="alt-header-actions">
                        <button class="alt-btn cluster-btn" onclick="enterClusterView()">🌌 Cluster View</button>
                        <button class="alt-modal-close" onclick="closeAltRealityModal()">&times;</button>
                    </div>
                </div>
                <div class="alt-modal-body">
                    <div class="alt-tabs">
                        <button class="alt-tab active" onclick="showAltTab('list')">My Realities</button>
                        <button class="alt-tab" onclick="showAltTab('create')">Create New</button>
                        <button class="alt-tab" onclick="showAltTab('compare')">Compare</button>
                        <button class="alt-tab future-tab" onclick="showAltTab('future')">Future</button>
                    </div>

                    <div id="alt-tab-list" class="alt-tab-content active">
                        <div id="alt-history-list">Loading...</div>
                    </div>

                    <div id="alt-tab-create" class="alt-tab-content">
                        <div class="alt-create-form">
                            <input type="text" id="alt-name" placeholder="Reality Name (e.g., 'What if I bought more TSLA')" />
                            <textarea id="alt-description" placeholder="Describe this alternate reality..."></textarea>

                            <h4>Modifications</h4>
                            <div id="alt-modifications"></div>
                            <button class="alt-btn secondary" onclick="addModification()">+ Add Modification</button>

                            <h4>Quick Scenarios</h4>
                            <div class="alt-quick-scenarios">
                                <button onclick="quickScenario('never-bought')">What if I never bought...</button>
                                <button onclick="quickScenario('doubled')">What if I doubled...</button>
                                <button onclick="quickScenario('sold-early')">What if I sold early...</button>
                            </div>

                            <button class="alt-btn primary" onclick="createAlternateHistory()">Create Reality</button>
                        </div>
                    </div>

                    <div id="alt-tab-compare" class="alt-tab-content">
                        <div class="alt-compare-selectors">
                            <select id="compare-history-1">
                                <option value="reality">Reality (Current Portfolio)</option>
                            </select>
                            <span class="vs">VS</span>
                            <select id="compare-history-2">
                                <option value="">Select alternate reality...</option>
                            </select>
                        </div>
                        <button class="alt-btn primary" onclick="compareRealities()">Compare</button>
                        <div id="compare-results"></div>
                    </div>

                    <div id="alt-tab-future" class="alt-tab-content">
                        <div class="future-controls">
                            <div class="future-source">
                                <label>Project from:</label>
                                <select id="future-source">
                                    <option value="reality">Current Reality</option>
                                </select>
                            </div>
                            <div class="future-years">
                                <label>Years to project:</label>
                                <select id="future-years">
                                    <option value="1">1 Year</option>
                                    <option value="2">2 Years</option>
                                    <option value="3" selected>3 Years</option>
                                    <option value="5">5 Years</option>
                                </select>
                            </div>
                            <div class="future-llm">
                                <label>
                                    <input type="checkbox" id="future-use-llm" checked>
                                    Use AI Analysis
                                </label>
                            </div>
                        </div>
                        <button class="alt-btn primary" onclick="generateFutureProjection()">Generate Projection</button>
                        <div id="future-loading" style="display: none; text-align: center; padding: 40px;">
                            <div class="loading-spinner"></div>
                            <p>Analyzing trends and generating projection...</p>
                        </div>
                        <div id="future-results"></div>

                        <h4 style="margin-top: 30px; color: #627eea;">Saved Projections</h4>
                        <div id="saved-projections">Loading...</div>
                    </div>
                </div>
            </div>
        `;

        // Add styles
        const styles = document.createElement('style');
        styles.textContent = `
            #alt-reality-modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: 1000; }
            #alt-reality-modal.active { display: block; }
            .alt-modal-backdrop { position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); backdrop-filter: blur(5px); }
            .alt-modal-content { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 90%; max-width: 700px; max-height: 80vh; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); border: 1px solid #627eea; border-radius: 16px; overflow: hidden; box-shadow: 0 0 50px rgba(98, 126, 234, 0.3); }
            .alt-modal-header { display: flex; justify-content: space-between; align-items: center; padding: 20px; border-bottom: 1px solid #627eea33; background: linear-gradient(90deg, #627eea22, transparent); }
            .alt-modal-header h2 { margin: 0; color: #627eea; font-size: 24px; }
            .alt-modal-close { background: none; border: none; color: #fff; font-size: 28px; cursor: pointer; opacity: 0.7; }
            .alt-modal-close:hover { opacity: 1; }
            .alt-modal-body { padding: 20px; overflow-y: auto; max-height: calc(80vh - 80px); }
            .alt-tabs { display: flex; gap: 10px; margin-bottom: 20px; }
            .alt-tab { background: #ffffff11; border: 1px solid #ffffff22; padding: 10px 20px; border-radius: 8px; color: #fff; cursor: pointer; transition: all 0.2s; }
            .alt-tab:hover { background: #627eea33; }
            .alt-tab.active { background: #627eea; border-color: #627eea; }
            .alt-tab-content { display: none; }
            .alt-tab-content.active { display: block; }
            .alt-history-item { background: #ffffff0a; border: 1px solid #ffffff15; border-radius: 8px; padding: 15px; margin-bottom: 10px; cursor: pointer; transition: all 0.2s; }
            .alt-history-item:hover { background: #627eea22; border-color: #627eea44; }
            .alt-history-item h4 { margin: 0 0 5px 0; color: #627eea; }
            .alt-history-item p { margin: 0; font-size: 13px; opacity: 0.7; }
            .alt-history-item .meta { display: flex; justify-content: space-between; margin-top: 10px; font-size: 12px; opacity: 0.5; }
            .alt-history-item .actions { margin-top: 10px; display: flex; gap: 10px; }
            .alt-btn { padding: 8px 16px; border-radius: 6px; border: none; cursor: pointer; font-weight: 500; transition: all 0.2s; }
            .alt-btn.primary { background: #627eea; color: white; }
            .alt-btn.primary:hover { background: #7c93ed; }
            .alt-btn.secondary { background: #ffffff15; color: white; border: 1px solid #ffffff30; }
            .alt-btn.secondary:hover { background: #ffffff25; }
            .alt-btn.danger { background: #ff4444; color: white; }
            .alt-btn.danger:hover { background: #ff6666; }
            .alt-create-form input, .alt-create-form textarea, .alt-create-form select { width: 100%; padding: 12px; margin-bottom: 15px; background: #ffffff0a; border: 1px solid #ffffff22; border-radius: 8px; color: white; font-size: 14px; }
            .alt-create-form textarea { min-height: 80px; resize: vertical; }
            .alt-create-form h4 { color: #627eea; margin: 20px 0 10px 0; }
            .alt-quick-scenarios { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; }
            .alt-quick-scenarios button { background: #ffffff0a; border: 1px solid #627eea44; padding: 8px 12px; border-radius: 6px; color: #627eea; cursor: pointer; font-size: 13px; }
            .alt-quick-scenarios button:hover { background: #627eea22; }
            .alt-modification { background: #ffffff0a; border: 1px solid #ffffff15; border-radius: 8px; padding: 15px; margin-bottom: 10px; }
            .alt-modification select, .alt-modification input { margin-bottom: 10px; }
            .alt-compare-selectors { display: flex; align-items: center; gap: 15px; margin-bottom: 20px; }
            .alt-compare-selectors select { flex: 1; padding: 12px; background: #ffffff0a; border: 1px solid #ffffff22; border-radius: 8px; color: white; }
            .vs { color: #627eea; font-weight: bold; font-size: 18px; }
            #compare-results { margin-top: 20px; }
            .compare-card { background: #ffffff0a; border-radius: 12px; padding: 20px; margin-bottom: 15px; }
            .compare-card h3 { color: #627eea; margin: 0 0 15px 0; }
            .compare-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #ffffff11; }
            .compare-row:last-child { border-bottom: none; }
            .compare-diff { font-weight: bold; }
            .compare-diff.positive { color: #00ff88; }
            .compare-diff.negative { color: #ff4444; }
            .empty-state { text-align: center; padding: 40px; opacity: 0.6; }
            .empty-state p { margin-bottom: 20px; }

            /* Future Projections Styles */
            .future-controls { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px; padding: 15px; background: #ffffff08; border-radius: 10px; }
            .future-controls label { display: block; margin-bottom: 5px; font-size: 12px; opacity: 0.7; }
            .future-controls select { width: 100%; padding: 10px; background: #ffffff0a; border: 1px solid #ffffff22; border-radius: 6px; color: white; }
            .future-llm { grid-column: span 2; display: flex; align-items: center; gap: 10px; }
            .future-llm label { display: flex; align-items: center; gap: 8px; margin: 0; cursor: pointer; }
            .loading-spinner { width: 40px; height: 40px; border: 3px solid #627eea33; border-top-color: #627eea; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 15px; }
            @keyframes spin { to { transform: rotate(360deg); } }

            .projection-result { margin-top: 20px; }
            .projection-summary { background: linear-gradient(135deg, #627eea22, #627eea08); border: 1px solid #627eea44; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
            .projection-summary h3 { color: #627eea; margin: 0 0 15px 0; }
            .projection-scenarios { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-top: 15px; }
            .scenario-card { background: #ffffff08; border-radius: 8px; padding: 15px; text-align: center; }
            .scenario-card.pessimistic { border-top: 3px solid #ff4444; }
            .scenario-card.base { border-top: 3px solid #627eea; }
            .scenario-card.optimistic { border-top: 3px solid #00ff88; }
            .scenario-card h4 { margin: 0 0 10px 0; font-size: 14px; opacity: 0.7; }
            .scenario-card .value { font-size: 24px; font-weight: bold; }
            .scenario-card.pessimistic .value { color: #ff4444; }
            .scenario-card.base .value { color: #627eea; }
            .scenario-card.optimistic .value { color: #00ff88; }

            .projection-analysis { background: #ffffff08; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
            .projection-analysis h3 { color: #627eea; margin: 0 0 15px 0; }
            .macro-outlook { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 15px; }
            .macro-item { background: #ffffff08; padding: 10px; border-radius: 6px; }
            .macro-item label { font-size: 11px; opacity: 0.6; display: block; margin-bottom: 3px; }
            .macro-item span { font-size: 13px; }

            .ticker-analyses { margin-top: 15px; }
            .ticker-analysis { background: #ffffff08; border-radius: 8px; padding: 15px; margin-bottom: 10px; }
            .ticker-analysis h4 { color: #627eea; margin: 0 0 10px 0; display: flex; justify-content: space-between; align-items: center; }
            .ticker-analysis .confidence { font-size: 11px; padding: 3px 8px; border-radius: 4px; background: #ffffff15; }
            .ticker-analysis .confidence.high { background: #00ff8833; color: #00ff88; }
            .ticker-analysis .confidence.medium { background: #ffaa0033; color: #ffaa00; }
            .ticker-analysis .confidence.low { background: #ff444433; color: #ff4444; }
            .ticker-growth-rates { display: flex; gap: 10px; margin: 10px 0; font-size: 13px; }
            .ticker-growth-rates span { padding: 4px 8px; border-radius: 4px; background: #ffffff08; }
            .ticker-catalysts { font-size: 12px; opacity: 0.8; margin-top: 10px; }
            .ticker-catalysts ul { margin: 5px 0; padding-left: 20px; }

            .projection-timeline { background: #ffffff08; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
            .projection-timeline h3 { color: #627eea; margin: 0 0 15px 0; }
            .timeline-chart { height: 200px; position: relative; }
            .timeline-bar { position: absolute; bottom: 0; background: linear-gradient(to top, #627eea, #627eea88); border-radius: 4px 4px 0 0; transition: height 0.3s; }
            .timeline-labels { display: flex; justify-content: space-between; margin-top: 10px; font-size: 11px; opacity: 0.6; }

            .saved-projection-item { background: #ffffff0a; border: 1px solid #ffffff15; border-radius: 8px; padding: 15px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }
            .saved-projection-item h4 { margin: 0; color: #627eea; font-size: 14px; }
            .saved-projection-item p { margin: 5px 0 0 0; font-size: 12px; opacity: 0.6; }
            .saved-projection-item .actions { display: flex; gap: 8px; }

            /* Cluster View Button */
            .alt-header-actions { display: flex; align-items: center; gap: 10px; }
            .cluster-btn { background: linear-gradient(135deg, #627eea, #9c27b0); padding: 8px 16px; font-size: 13px; }
            .cluster-btn:hover { background: linear-gradient(135deg, #7c93ed, #ba68c8); }
        `;
        document.head.appendChild(styles);
        document.body.appendChild(modal);
    }

    modal.classList.add('active');
    loadAlternateHistories();
}
window.showAlternateRealityModal = showAlternateRealityModal;

function closeAltRealityModal() {
    const modal = document.getElementById('alt-reality-modal');
    if (modal) modal.classList.remove('active');
}
window.closeAltRealityModal = closeAltRealityModal;

function showAltTab(tabName) {
    document.querySelectorAll('.alt-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.alt-tab-content').forEach(c => c.classList.remove('active'));
    document.querySelector(`.alt-tab[onclick="showAltTab('${tabName}')"]`).classList.add('active');
    document.getElementById(`alt-tab-${tabName}`).classList.add('active');

    if (tabName === 'compare') loadCompareOptions();
    if (tabName === 'future') {
        loadFutureSourceOptions();
        loadSavedProjections();
    }
}
window.showAltTab = showAltTab;

async function loadAlternateHistories() {
    try {
        const response = await fetch('/api/alt-history');
        const data = await response.json();
        altHistoryData.histories = data.histories || [];

        const container = document.getElementById('alt-history-list');

        if (altHistoryData.histories.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <p>No alternate realities created yet.</p>
                    <button class="alt-btn primary" onclick="showAltTab('create')">Create Your First Reality</button>
                </div>
            `;
            return;
        }

        container.innerHTML = altHistoryData.histories.map(h => `
            <div class="alt-history-item" onclick="viewAlternateHistory('${h.id}')">
                <h4>${h.name}</h4>
                <p>${h.description || 'No description'}</p>
                <div class="meta">
                    <span>Created: ${new Date(h.created_at).toLocaleDateString()}</span>
                    <span>${h.modifications?.length || 0} modifications</span>
                </div>
                <div class="actions" onclick="event.stopPropagation()">
                    <button class="alt-btn secondary" onclick="compareWithReality('${h.id}')">Compare to Reality</button>
                    <button class="alt-btn danger" onclick="deleteAlternateHistory('${h.id}')">Delete</button>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Failed to load alternate histories:', error);
        document.getElementById('alt-history-list').innerHTML = '<p style="color: #ff4444;">Failed to load alternate histories</p>';
    }
}

// Track current alternate view state
let currentAltViewHistoryId = null;

async function viewAlternateHistory(historyId) {
    try {
        currentAltViewHistoryId = historyId;

        const response = await fetch(`/api/alt-history/${historyId}`);
        const data = await response.json();

        // Show state comparison
        const comparison = await fetch(`/api/alt-history/${historyId}/compare/reality`).then(r => r.json());
        showComparisonResults(comparison);
        showAltTab('compare');

        // Enter alternate view mode
        enterAltViewMode(data.name || historyId);
    } catch (error) {
        console.error('Failed to view history:', error);
    }
}
window.viewAlternateHistory = viewAlternateHistory;

// ==================== ALTERNATE VIEW MODE ====================
function enterAltViewMode(historyName = 'Alternate Reality') {
    document.body.classList.add('alt-view-mode');

    // Update the status display
    const statusEl = document.getElementById('system-status');
    if (statusEl) {
        statusEl.innerHTML = `<span style="color: #627eea;">VIEWING: ${historyName.toUpperCase()}</span>`;
    }

    // Close the alt reality modal
    closeAltRealityModal();

    // Auto-fit the view
    setTimeout(() => autoFitSystem(true), 300);
}
window.enterAltViewMode = enterAltViewMode;

function exitAltViewMode() {
    document.body.classList.remove('alt-view-mode');
    currentAltViewHistoryId = null;

    // Clear the status display
    const statusEl = document.getElementById('system-status');
    if (statusEl) {
        statusEl.textContent = '';
    }

    // Reset camera to default
    gsap.to(camera.position, {
        x: DEFAULT_CAMERA_POS.x,
        y: DEFAULT_CAMERA_POS.y,
        z: DEFAULT_CAMERA_POS.z,
        duration: 1,
        ease: "power2.inOut"
    });
    gsap.to(controls.target, {
        x: DEFAULT_TARGET.x,
        y: DEFAULT_TARGET.y,
        z: DEFAULT_TARGET.z,
        duration: 1,
        ease: "power2.inOut"
    });
}
window.exitAltViewMode = exitAltViewMode;

function toggleProjectionOverlay() {
    const btn = document.getElementById('btn-proj-overlay');
    if (!currentAltViewHistoryId) {
        alert('No alternate history selected');
        return;
    }

    // Toggle overlay showing projection on the 3D view
    btn.classList.toggle('active');
    if (btn.classList.contains('active')) {
        btn.textContent = 'Hide Projections';
        // Could add 3D projection visualization here
    } else {
        btn.textContent = 'Show Projections';
    }
}
window.toggleProjectionOverlay = toggleProjectionOverlay;

async function deleteAlternateHistory(historyId) {
    if (!confirm('Delete this alternate reality? This cannot be undone.')) return;

    try {
        await fetch(`/api/alt-history/${historyId}`, { method: 'DELETE' });
        loadAlternateHistories();
        loadCompareOptions();
    } catch (error) {
        console.error('Failed to delete history:', error);
    }
}
window.deleteAlternateHistory = deleteAlternateHistory;

function loadCompareOptions() {
    const select1 = document.getElementById('compare-history-1');
    const select2 = document.getElementById('compare-history-2');

    const options = altHistoryData.histories.map(h =>
        `<option value="${h.id}">${h.name}</option>`
    ).join('');

    select1.innerHTML = `<option value="reality">Reality (Current Portfolio)</option>${options}`;
    select2.innerHTML = `<option value="">Select alternate reality...</option><option value="reality">Reality</option>${options}`;
}

async function compareRealities() {
    const id1 = document.getElementById('compare-history-1').value;
    const id2 = document.getElementById('compare-history-2').value;

    if (!id2) {
        alert('Please select a second reality to compare');
        return;
    }

    try {
        const response = await fetch(`/api/alt-history/${id1}/compare/${id2}`);
        const data = await response.json();
        showComparisonResults(data);
    } catch (error) {
        console.error('Failed to compare:', error);
    }
}
window.compareRealities = compareRealities;

async function compareWithReality(historyId) {
    try {
        const response = await fetch(`/api/alt-history/${historyId}/compare/reality`);
        const data = await response.json();
        showComparisonResults(data);
        showAltTab('compare');

        // Set the selectors
        document.getElementById('compare-history-1').value = 'reality';
        document.getElementById('compare-history-2').value = historyId;
    } catch (error) {
        console.error('Failed to compare:', error);
    }
}
window.compareWithReality = compareWithReality;

function showComparisonResults(data) {
    const container = document.getElementById('compare-results');
    const diff = data.comparison;
    const h1 = data.history_1;
    const h2 = data.history_2;
    const divergence = data.divergence || {};
    const projections = data.projections || null;
    const historicalTimeline = data.historical_timeline || [];

    const formatMoney = n => '$' + Math.abs(n).toLocaleString('en-US', { maximumFractionDigits: 0 });
    const formatMoneyWithSign = n => (n >= 0 ? '+$' : '-$') + Math.abs(n).toLocaleString('en-US', { maximumFractionDigits: 0 });
    const diffClass = n => n >= 0 ? 'positive' : 'negative';
    const formatPct = n => (n >= 0 ? '+' : '') + n.toFixed(1) + '%';

    // Current State Comparison
    let html = `
        <div class="compare-section">
            <h3 class="section-header">CURRENT STATE</h3>
            <div class="compare-grid">
                <div class="compare-card">
                    <h4>Portfolio Value</h4>
                    <div class="compare-row">
                        <span>${h1.name}</span>
                        <span>${formatMoney(h1.total_value)}</span>
                    </div>
                    <div class="compare-row">
                        <span>${h2.name}</span>
                        <span>${formatMoney(h2.total_value)}</span>
                    </div>
                    <div class="compare-row highlight">
                        <span>Difference</span>
                        <span class="compare-diff ${diffClass(diff.total_value_diff)}">${formatMoneyWithSign(diff.total_value_diff)}</span>
                    </div>
                </div>

                <div class="compare-card">
                    <h4>YTD Income</h4>
                    <div class="compare-row">
                        <span>${h1.name}</span>
                        <span>${formatMoney(h1.ytd_income)}</span>
                    </div>
                    <div class="compare-row">
                        <span>${h2.name}</span>
                        <span>${formatMoney(h2.ytd_income)}</span>
                    </div>
                    <div class="compare-row highlight">
                        <span>Difference</span>
                        <span class="compare-diff ${diffClass(diff.income_diff)}">${formatMoneyWithSign(diff.income_diff)}</span>
                    </div>
                </div>
            </div>
        </div>`;

    // Divergence Points
    if (divergence.points && divergence.points.length > 0) {
        html += `
        <div class="compare-section">
            <h3 class="section-header">TIMELINE DIVERGENCE [${divergence.total_divergent_events} EVENTS]</h3>
            <div class="divergence-list">
                ${divergence.points.slice(0, 10).map(p => `
                    <div class="divergence-item ${p.in_history === 'modified' ? 'modified' : p.in_history === 'history_1_only' ? 'removed' : 'added'}">
                        <div class="divergence-badge">${p.in_history === 'history_1_only' ? 'REMOVED' : p.in_history === 'history_2_only' ? 'ADDED' : 'MODIFIED'}</div>
                        <div class="divergence-content">
                            <span class="divergence-type">${p.type}</span>
                            <span class="divergence-desc">${p.description}</span>
                            <span class="divergence-date">${new Date(p.timestamp).toLocaleDateString()}</span>
                        </div>
                    </div>
                `).join('')}
                ${divergence.points.length > 10 ? `<p class="more-items">...and ${divergence.points.length - 10} more divergent events</p>` : ''}
            </div>
        </div>`;
    } else {
        html += `
        <div class="compare-section">
            <h3 class="section-header">TIMELINE DIVERGENCE</h3>
            <p class="no-divergence">No divergence detected - these histories are identical</p>
        </div>`;
    }

    // Historical Timeline Chart with reduced exaggeration and interpolation
    if (historicalTimeline.length > 0) {
        // Calculate scale with reduced exaggeration (minimum 60% baseline)
        const allValues = historicalTimeline.flatMap(x => [x.history_1.total_value, x.history_2.total_value]).filter(v => v > 0);
        const maxVal = Math.max(...allValues);
        const minVal = Math.min(...allValues);
        // Scale so minimum is 60% and max is 100% - reduces visual exaggeration
        const scaleValue = (v) => {
            if (maxVal === minVal) return 80;
            return 60 + ((v - minVal) / (maxVal - minVal)) * 40;
        };

        // Prepare timeline data for interpolation
        const timelineData = historicalTimeline.map(t => ({
            h1: scaleValue(t.history_1.total_value),
            h2: scaleValue(t.history_2.total_value),
            date: t.date,
            v1: t.history_1.total_value,
            v2: t.history_2.total_value,
            diff: t.diff
        }));

        html += `
        <div class="compare-section">
            <h3 class="section-header">HISTORICAL VALUE DIVERGENCE</h3>
            <div class="timeline-speed-control">
                <button class="speed-btn" onclick="adjustPlaybackSpeed(-1)">◀</button>
                <span class="speed-display" id="playback-speed-display">1 mo/sec</span>
                <button class="speed-btn" onclick="adjustPlaybackSpeed(1)">▶</button>
            </div>
            <div class="timeline-chart" id="historical-timeline-chart">
                <div class="timeline-playback">
                    <button class="timeline-play-btn" id="hist-play-btn" onclick="toggleHistoricalPlayback()">▶</button>
                    <input type="range" class="timeline-scrubber" id="hist-scrubber"
                           min="0" max="${timelineData.length - 1}" value="${timelineData.length - 1}" step="0.01"
                           oninput="scrubHistoricalTimeline(this.value)">
                    <span class="timeline-date" id="hist-date">${timelineData[timelineData.length - 1]?.date || 'Now'}</span>
                </div>
                <div class="timeline-values">
                    <div class="timeline-value-display">
                        <span class="value-label">${h1.name}:</span>
                        <span class="value-amount" id="hist-value-1">${formatMoney(timelineData[timelineData.length - 1]?.v1 || 0)}</span>
                    </div>
                    <div class="timeline-value-display">
                        <span class="value-label">${h2.name}:</span>
                        <span class="value-amount" id="hist-value-2">${formatMoney(timelineData[timelineData.length - 1]?.v2 || 0)}</span>
                    </div>
                    <div class="timeline-value-display diff">
                        <span class="value-label">Diff:</span>
                        <span class="value-amount" id="hist-diff">${formatMoneyWithSign(timelineData[timelineData.length - 1]?.diff || 0)}</span>
                    </div>
                </div>
                <div class="timeline-bars-container">
                    <div class="timeline-bar-single history-1" id="hist-bar-1" style="height: ${timelineData[timelineData.length - 1]?.h1 || 80}%"></div>
                    <div class="timeline-bar-single history-2" id="hist-bar-2" style="height: ${timelineData[timelineData.length - 1]?.h2 || 80}%"></div>
                </div>
                <div class="timeline-legend">
                    <span class="legend-item"><span class="legend-color history-1"></span>${h1.name}</span>
                    <span class="legend-item"><span class="legend-color history-2"></span>${h2.name}</span>
                </div>
            </div>
        </div>`;

        // Store timeline data for scrubbing
        window.historicalTimelineData = timelineData;
        window.historicalTimelineNames = { h1: h1.name, h2: h2.name };
    }

    // Future Projections
    if (projections) {
        const proj1 = projections.history_1_projection;
        const proj2 = projections.history_2_projection;
        const projTimeline = projections.timeline || [];

        html += `
        <div class="compare-section">
            <h3 class="section-header">${projections.years}-YEAR FUTURE PROJECTION</h3>
            <div class="compare-grid">
                <div class="compare-card projection-card">
                    <h4>${h1.name}</h4>
                    <div class="projection-value">${formatMoney(proj1.projected_value)}</div>
                    <div class="projection-growth ${diffClass(proj1.growth_from_current)}">${formatPct(proj1.growth_from_current)} projected growth</div>
                    <div class="projection-date">by ${proj1.end_date}</div>
                </div>
                <div class="compare-card projection-card">
                    <h4>${h2.name}</h4>
                    <div class="projection-value">${formatMoney(proj2.projected_value)}</div>
                    <div class="projection-growth ${diffClass(proj2.growth_from_current)}">${formatPct(proj2.growth_from_current)} projected growth</div>
                    <div class="projection-date">by ${proj2.end_date}</div>
                </div>
            </div>
            <div class="projection-diff-summary">
                <span>Projected Difference in ${projections.years} Years:</span>
                <span class="compare-diff ${diffClass(projections.projected_diff)}">${formatMoneyWithSign(projections.projected_diff)}</span>
            </div>
            ${projTimeline.length > 0 ? (() => {
                // Reduced exaggeration for projection chart too
                const projValues = projTimeline.flatMap(x => [x.value_1, x.value_2]).filter(v => v > 0);
                const projMax = Math.max(...projValues);
                const projMin = Math.min(...projValues);
                const scaleProjValue = (v) => {
                    if (projMax === projMin) return 80;
                    return 60 + ((v - projMin) / (projMax - projMin)) * 40;
                };

                // Prepare projection data for interpolation
                const projData = projTimeline.map(t => ({
                    h1: scaleProjValue(t.value_1),
                    h2: scaleProjValue(t.value_2),
                    date: t.date,
                    v1: t.value_1,
                    v2: t.value_2,
                    diff: t.diff
                }));

                // Store for scrubbing
                window.projectionTimelineData = projData;

                return `
            <div class="projection-timeline-chart">
                <div class="timeline-playback">
                    <button class="timeline-play-btn" id="proj-play-btn" onclick="toggleProjectionPlayback()">▶</button>
                    <input type="range" class="timeline-scrubber" id="proj-scrubber"
                           min="0" max="${projData.length - 1}" value="0" step="0.01"
                           oninput="scrubProjectionTimeline(this.value)">
                    <span class="timeline-date" id="proj-date">${projData[0]?.date || 'Now'}</span>
                </div>
                <div class="timeline-values">
                    <div class="timeline-value-display">
                        <span class="value-label">${h1.name}:</span>
                        <span class="value-amount" id="proj-value-1">${formatMoney(projData[0]?.v1 || 0)}</span>
                    </div>
                    <div class="timeline-value-display">
                        <span class="value-label">${h2.name}:</span>
                        <span class="value-amount" id="proj-value-2">${formatMoney(projData[0]?.v2 || 0)}</span>
                    </div>
                    <div class="timeline-value-display diff">
                        <span class="value-label">Diff:</span>
                        <span class="value-amount" id="proj-diff">${formatMoneyWithSign(projData[0]?.diff || 0)}</span>
                    </div>
                </div>
                <div class="timeline-bars-container">
                    <div class="timeline-bar-single history-1" id="proj-bar-1" style="height: ${projData[0]?.h1 || 80}%"></div>
                    <div class="timeline-bar-single history-2" id="proj-bar-2" style="height: ${projData[0]?.h2 || 80}%"></div>
                </div>
                <div class="timeline-labels">
                    <span>Now</span>
                    <span>Year 1</span>
                    <span>Year 2</span>
                    <span>Year 3</span>
                </div>
            </div>`;
            })() : ''}
        </div>`;
    }

    // Holdings Differences
    const holdingsDiff = Object.entries(diff.holdings_diff);
    if (holdingsDiff.length > 0) {
        html += `
        <div class="compare-section">
            <h3 class="section-header">HOLDINGS DIFFERENCES</h3>
            <div class="holdings-diff-list">
                ${holdingsDiff.map(([ticker, d]) => `
                    <div class="holdings-diff-item">
                        <span class="ticker">${ticker}</span>
                        <span class="shares">${d.shares_1.toFixed(1)} → ${d.shares_2.toFixed(1)} shares</span>
                        <span class="value-diff compare-diff ${diffClass(d.value_diff)}">${formatMoneyWithSign(d.value_diff)}</span>
                    </div>
                `).join('')}
            </div>
        </div>`;
    }

    container.innerHTML = html;
}

// ==================== TIMELINE SCRUBBING & PLAYBACK ====================
let historicalPlaybackActive = false;
let historicalPlaybackRAF = null;
let historicalPlaybackStartTime = null;
let historicalPlaybackStartPosition = 0;

let projectionPlaybackActive = false;
let projectionPlaybackRAF = null;
let projectionPlaybackStartTime = null;
let projectionPlaybackStartPosition = 0;

// Playback speed: days of timeline per second of real time
// Default: 30 days per second (1 month per second)
let timelinePlaybackSpeed = 30;

// Linear interpolation helper
function lerp(a, b, t) {
    return a + (b - a) * t;
}

// Parse date string to timestamp
function parseTimelineDate(dateStr) {
    // Handle various date formats
    const d = new Date(dateStr);
    return isNaN(d.getTime()) ? Date.now() : d.getTime();
}

// Calculate timeline span in days
function getTimelineSpanDays(data) {
    if (!data || data.length < 2) return 1;
    const firstDate = parseTimelineDate(data[0].date);
    const lastDate = parseTimelineDate(data[data.length - 1].date);
    return Math.max(1, (lastDate - firstDate) / (1000 * 60 * 60 * 24));
}

// Find position in timeline based on interpolated date
function findTimelinePosition(data, targetTime) {
    if (!data || data.length === 0) return 0;
    if (data.length === 1) return 0;

    const firstTime = parseTimelineDate(data[0].date);
    const lastTime = parseTimelineDate(data[data.length - 1].date);

    if (targetTime <= firstTime) return 0;
    if (targetTime >= lastTime) return data.length - 1;

    // Find which segment we're in and interpolate
    for (let i = 0; i < data.length - 1; i++) {
        const t1 = parseTimelineDate(data[i].date);
        const t2 = parseTimelineDate(data[i + 1].date);

        if (targetTime >= t1 && targetTime <= t2) {
            const segmentProgress = (targetTime - t1) / (t2 - t1);
            return i + segmentProgress;
        }
    }

    return data.length - 1;
}

// Interpolate date string between two dates
function interpolateDate(date1Str, date2Str, t) {
    const d1 = parseTimelineDate(date1Str);
    const d2 = parseTimelineDate(date2Str);
    const interpolatedTime = d1 + (d2 - d1) * t;
    const d = new Date(interpolatedTime);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

// Format money for display
function formatMoneyDisplay(n) {
    return '$' + Math.abs(n).toLocaleString('en-US', { maximumFractionDigits: 0 });
}

function formatMoneyWithSignDisplay(n) {
    return (n >= 0 ? '+$' : '-$') + Math.abs(n).toLocaleString('en-US', { maximumFractionDigits: 0 });
}

// Update playback speed display
function updateSpeedDisplay() {
    const speedEl = document.getElementById('playback-speed-display');
    if (speedEl) {
        if (timelinePlaybackSpeed >= 30) {
            speedEl.textContent = `${Math.round(timelinePlaybackSpeed / 30)} mo/sec`;
        } else if (timelinePlaybackSpeed >= 7) {
            speedEl.textContent = `${Math.round(timelinePlaybackSpeed / 7)} wk/sec`;
        } else {
            speedEl.textContent = `${timelinePlaybackSpeed} days/sec`;
        }
    }
}

// Adjust playback speed
function adjustPlaybackSpeed(delta) {
    const speeds = [7, 14, 30, 60, 90, 180, 365]; // 1wk, 2wk, 1mo, 2mo, 3mo, 6mo, 1yr per second
    const currentIndex = speeds.findIndex(s => s >= timelinePlaybackSpeed);
    const newIndex = Math.max(0, Math.min(speeds.length - 1, currentIndex + delta));
    timelinePlaybackSpeed = speeds[newIndex];
    updateSpeedDisplay();
}
window.adjustPlaybackSpeed = adjustPlaybackSpeed;

// Scrub through historical timeline with interpolation
function scrubHistoricalTimeline(value) {
    const data = window.historicalTimelineData;
    if (!data || data.length === 0) return;

    const floatIndex = parseFloat(value);
    const lowerIndex = Math.max(0, Math.floor(floatIndex));
    const upperIndex = Math.min(lowerIndex + 1, data.length - 1);
    const t = floatIndex - lowerIndex; // Interpolation factor 0-1

    // Interpolate between frames
    const lower = data[lowerIndex];
    const upper = data[upperIndex];

    const h1 = lerp(lower.h1, upper.h1, t);
    const h2 = lerp(lower.h2, upper.h2, t);
    const v1 = lerp(lower.v1, upper.v1, t);
    const v2 = lerp(lower.v2, upper.v2, t);
    const diff = lerp(lower.diff, upper.diff, t);

    // Update bars with smooth transition
    const bar1 = document.getElementById('hist-bar-1');
    const bar2 = document.getElementById('hist-bar-2');
    if (bar1) bar1.style.height = h1 + '%';
    if (bar2) bar2.style.height = h2 + '%';

    // Update values with interpolated date
    const dateEl = document.getElementById('hist-date');
    const v1El = document.getElementById('hist-value-1');
    const v2El = document.getElementById('hist-value-2');
    const diffEl = document.getElementById('hist-diff');

    if (dateEl) dateEl.textContent = interpolateDate(lower.date, upper.date, t);
    if (v1El) v1El.textContent = formatMoneyDisplay(v1);
    if (v2El) v2El.textContent = formatMoneyDisplay(v2);
    if (diffEl) {
        diffEl.textContent = formatMoneyWithSignDisplay(diff);
        diffEl.className = 'value-amount ' + (diff >= 0 ? 'positive' : 'negative');
    }
}
window.scrubHistoricalTimeline = scrubHistoricalTimeline;

function animateHistoricalPlayback(timestamp) {
    if (!historicalPlaybackActive) return;

    const data = window.historicalTimelineData;
    const scrubber = document.getElementById('hist-scrubber');
    if (!data || data.length === 0 || !scrubber) return;

    // Initialize start time on first frame
    if (!historicalPlaybackStartTime) {
        historicalPlaybackStartTime = timestamp;
    }

    // Calculate elapsed real time in seconds
    const elapsedSeconds = (timestamp - historicalPlaybackStartTime) / 1000;

    // Calculate how many days of timeline have passed
    const daysPassed = elapsedSeconds * timelinePlaybackSpeed;

    // Get the starting date and calculate target date
    const startPosition = historicalPlaybackStartPosition;
    const startDateIndex = Math.floor(startPosition);
    const startDate = parseTimelineDate(data[startDateIndex].date);
    const targetDate = startDate + (daysPassed * 24 * 60 * 60 * 1000);

    // Find position in timeline for this date
    const position = findTimelinePosition(data, targetDate);

    if (position >= data.length - 1) {
        // Reached the end
        scrubber.value = data.length - 1;
        scrubHistoricalTimeline(data.length - 1);
        toggleHistoricalPlayback();
        return;
    }

    scrubber.value = position;
    scrubHistoricalTimeline(position);

    // Continue animation
    historicalPlaybackRAF = requestAnimationFrame(animateHistoricalPlayback);
}

function toggleHistoricalPlayback() {
    const btn = document.getElementById('hist-play-btn');
    const scrubber = document.getElementById('hist-scrubber');
    const data = window.historicalTimelineData;

    if (!data || data.length === 0) return;

    if (historicalPlaybackActive) {
        // Stop playback
        historicalPlaybackActive = false;
        if (historicalPlaybackRAF) {
            cancelAnimationFrame(historicalPlaybackRAF);
            historicalPlaybackRAF = null;
        }
        btn.textContent = '▶';
    } else {
        // Start playback
        historicalPlaybackActive = true;
        btn.textContent = '⏸';

        // Reset to start if at end
        if (parseFloat(scrubber.value) >= data.length - 1) {
            scrubber.value = 0;
        }

        // Store starting position and reset timing
        historicalPlaybackStartPosition = parseFloat(scrubber.value);
        historicalPlaybackStartTime = null;

        // Start animation loop
        historicalPlaybackRAF = requestAnimationFrame(animateHistoricalPlayback);
    }
}
window.toggleHistoricalPlayback = toggleHistoricalPlayback;

// Scrub through projection timeline with interpolation
function scrubProjectionTimeline(value) {
    const data = window.projectionTimelineData;
    if (!data || data.length === 0) return;

    const floatIndex = parseFloat(value);
    const lowerIndex = Math.max(0, Math.floor(floatIndex));
    const upperIndex = Math.min(lowerIndex + 1, data.length - 1);
    const t = floatIndex - lowerIndex;

    const lower = data[lowerIndex];
    const upper = data[upperIndex];

    const h1 = lerp(lower.h1, upper.h1, t);
    const h2 = lerp(lower.h2, upper.h2, t);
    const v1 = lerp(lower.v1, upper.v1, t);
    const v2 = lerp(lower.v2, upper.v2, t);
    const diff = lerp(lower.diff, upper.diff, t);

    // Update bars
    const bar1 = document.getElementById('proj-bar-1');
    const bar2 = document.getElementById('proj-bar-2');
    if (bar1) bar1.style.height = h1 + '%';
    if (bar2) bar2.style.height = h2 + '%';

    // Update values with interpolated date
    const dateEl = document.getElementById('proj-date');
    const v1El = document.getElementById('proj-value-1');
    const v2El = document.getElementById('proj-value-2');
    const diffEl = document.getElementById('proj-diff');

    if (dateEl) dateEl.textContent = interpolateDate(lower.date, upper.date, t);
    if (v1El) v1El.textContent = formatMoneyDisplay(v1);
    if (v2El) v2El.textContent = formatMoneyDisplay(v2);
    if (diffEl) {
        diffEl.textContent = formatMoneyWithSignDisplay(diff);
        diffEl.className = 'value-amount ' + (diff >= 0 ? 'positive' : 'negative');
    }
}
window.scrubProjectionTimeline = scrubProjectionTimeline;

function animateProjectionPlayback(timestamp) {
    if (!projectionPlaybackActive) return;

    const data = window.projectionTimelineData;
    const scrubber = document.getElementById('proj-scrubber');
    if (!data || data.length === 0 || !scrubber) return;

    if (!projectionPlaybackStartTime) {
        projectionPlaybackStartTime = timestamp;
    }

    const elapsedSeconds = (timestamp - projectionPlaybackStartTime) / 1000;
    const daysPassed = elapsedSeconds * timelinePlaybackSpeed;

    const startPosition = projectionPlaybackStartPosition;
    const startDateIndex = Math.floor(startPosition);
    const startDate = parseTimelineDate(data[startDateIndex].date);
    const targetDate = startDate + (daysPassed * 24 * 60 * 60 * 1000);

    const position = findTimelinePosition(data, targetDate);

    if (position >= data.length - 1) {
        scrubber.value = data.length - 1;
        scrubProjectionTimeline(data.length - 1);
        toggleProjectionPlayback();
        return;
    }

    scrubber.value = position;
    scrubProjectionTimeline(position);

    projectionPlaybackRAF = requestAnimationFrame(animateProjectionPlayback);
}

function toggleProjectionPlayback() {
    const btn = document.getElementById('proj-play-btn');
    const scrubber = document.getElementById('proj-scrubber');
    const data = window.projectionTimelineData;

    if (!data || data.length === 0) return;

    if (projectionPlaybackActive) {
        projectionPlaybackActive = false;
        if (projectionPlaybackRAF) {
            cancelAnimationFrame(projectionPlaybackRAF);
            projectionPlaybackRAF = null;
        }
        btn.textContent = '▶';
    } else {
        projectionPlaybackActive = true;
        btn.textContent = '⏸';

        if (parseFloat(scrubber.value) >= data.length - 1) {
            scrubber.value = 0;
        }

        projectionPlaybackStartPosition = parseFloat(scrubber.value);
        projectionPlaybackStartTime = null;

        projectionPlaybackRAF = requestAnimationFrame(animateProjectionPlayback);
    }
}
window.toggleProjectionPlayback = toggleProjectionPlayback;

let modificationCount = 0;

function addModification() {
    const container = document.getElementById('alt-modifications');
    const id = modificationCount++;

    const div = document.createElement('div');
    div.className = 'alt-modification';
    div.id = `mod-${id}`;
    div.innerHTML = `
        <select onchange="updateModificationFields(${id})">
            <option value="">Select modification type...</option>
            <option value="remove_ticker">Remove all trades for ticker</option>
            <option value="scale_position">Scale position size</option>
            <option value="add_trade">Add hypothetical trade</option>
        </select>
        <div id="mod-fields-${id}"></div>
        <button class="alt-btn danger" onclick="document.getElementById('mod-${id}').remove()" style="margin-top: 10px;">Remove</button>
    `;
    container.appendChild(div);
}
window.addModification = addModification;

function updateModificationFields(id) {
    const select = document.querySelector(`#mod-${id} select`);
    const fieldsContainer = document.getElementById(`mod-fields-${id}`);
    const type = select.value;

    const tickers = portfolioData?.holdings?.map(h => h.ticker) || [];
    const tickerOptions = tickers.map(t => `<option value="${t}">${t}</option>`).join('');

    if (type === 'remove_ticker') {
        fieldsContainer.innerHTML = `
            <select data-field="ticker">
                <option value="">Select ticker to remove...</option>
                ${tickerOptions}
            </select>
        `;
    } else if (type === 'scale_position') {
        fieldsContainer.innerHTML = `
            <select data-field="ticker">
                <option value="">Select ticker...</option>
                ${tickerOptions}
            </select>
            <input type="number" data-field="scale" placeholder="Scale factor (e.g., 2.0 = double, 0.5 = half)" step="0.1" />
        `;
    } else if (type === 'add_trade') {
        fieldsContainer.innerHTML = `
            <select data-field="action">
                <option value="BUY">BUY</option>
                <option value="SELL">SELL</option>
            </select>
            <input type="text" data-field="ticker" placeholder="Ticker (e.g., NVDA)" />
            <input type="number" data-field="shares" placeholder="Shares" />
            <input type="number" data-field="price" placeholder="Price per share" step="0.01" />
            <input type="date" data-field="timestamp" />
        `;
    } else {
        fieldsContainer.innerHTML = '';
    }
}
window.updateModificationFields = updateModificationFields;

async function createAlternateHistory() {
    const name = document.getElementById('alt-name').value;
    const description = document.getElementById('alt-description').value;

    if (!name) {
        alert('Please enter a name for this alternate reality');
        return;
    }

    // Collect modifications
    const modifications = [];
    document.querySelectorAll('.alt-modification').forEach(mod => {
        const type = mod.querySelector('select').value;
        if (!type) return;

        const modification = { type };
        mod.querySelectorAll('[data-field]').forEach(field => {
            const fieldName = field.dataset.field;
            let value = field.value;
            if (field.type === 'number') value = parseFloat(value);
            if (value) modification[fieldName] = value;
        });
        modifications.push(modification);
    });

    try {
        const response = await fetch('/api/alt-history', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, description, modifications })
        });

        const data = await response.json();

        if (data.success) {
            // Clear form
            document.getElementById('alt-name').value = '';
            document.getElementById('alt-description').value = '';
            document.getElementById('alt-modifications').innerHTML = '';
            modificationCount = 0;

            // Switch to list view
            showAltTab('list');
            loadAlternateHistories();
        } else {
            alert('Failed to create alternate reality: ' + (data.detail || 'Unknown error'));
        }
    } catch (error) {
        console.error('Failed to create history:', error);
        alert('Failed to create alternate reality');
    }
}
window.createAlternateHistory = createAlternateHistory;

async function quickScenario(scenario) {
    const tickers = portfolioData?.holdings?.map(h => h.ticker) || [];
    const ticker = prompt(`Enter ticker symbol:\n\nAvailable: ${tickers.join(', ')}`);

    if (!ticker) return;

    try {
        let endpoint;
        if (scenario === 'never-bought') {
            endpoint = `/api/alt-history/what-if/never-bought?ticker=${ticker}`;
        } else if (scenario === 'doubled') {
            endpoint = `/api/alt-history/what-if/doubled-position?ticker=${ticker}`;
        } else {
            alert('Coming soon!');
            return;
        }

        const response = await fetch(endpoint, { method: 'POST' });
        const data = await response.json();

        if (data.history) {
            showComparisonResults(data.comparison);
            showAltTab('compare');
            loadAlternateHistories();
        }
    } catch (error) {
        console.error('Quick scenario failed:', error);
    }
}
window.quickScenario = quickScenario;

// ============ Future Projection Functions ============

function loadFutureSourceOptions() {
    const select = document.getElementById('future-source');
    const options = altHistoryData.histories.map(h =>
        `<option value="${h.id}">${h.name}</option>`
    ).join('');
    select.innerHTML = `<option value="reality">Current Reality</option>${options}`;
}

async function loadSavedProjections() {
    const container = document.getElementById('saved-projections');
    try {
        const response = await fetch('/api/alt-history/projections');
        const data = await response.json();
        const projections = data.projections || [];

        if (projections.length === 0) {
            container.innerHTML = '<p style="opacity: 0.6; text-align: center;">No saved projections yet.</p>';
            return;
        }

        container.innerHTML = projections.map(p => `
            <div class="saved-projection-item">
                <div>
                    <h4>${p.history_id === 'reality' ? 'Reality' : p.history_id} - ${p.years}yr Projection</h4>
                    <p>Created: ${new Date(p.created_at).toLocaleDateString()} | Ends: ${new Date(p.end_date).toLocaleDateString()}</p>
                </div>
                <div class="actions">
                    <button class="alt-btn secondary" onclick="viewProjection('${p.id}')">View</button>
                    <button class="alt-btn danger" onclick="deleteProjection('${p.id}')">Delete</button>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Failed to load projections:', error);
        container.innerHTML = '<p style="color: #ff4444;">Failed to load projections</p>';
    }
}
window.loadSavedProjections = loadSavedProjections;

async function generateFutureProjection() {
    const historyId = document.getElementById('future-source').value;
    const years = parseInt(document.getElementById('future-years').value);
    const useLlm = document.getElementById('future-use-llm').checked;

    const loading = document.getElementById('future-loading');
    const results = document.getElementById('future-results');

    loading.style.display = 'block';
    results.innerHTML = '';

    try {
        const response = await fetch('/api/alt-history/projections/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                history_id: historyId,
                years: years,
                use_llm: useLlm
            })
        });

        const data = await response.json();
        loading.style.display = 'none';

        if (data.error) {
            results.innerHTML = `<p style="color: #ff4444;">Error: ${data.error}</p>`;
            return;
        }

        showProjectionResults(data);
        loadSavedProjections();
    } catch (error) {
        console.error('Failed to generate projection:', error);
        loading.style.display = 'none';
        results.innerHTML = `<p style="color: #ff4444;">Failed to generate projection: ${error.message}</p>`;
    }
}
window.generateFutureProjection = generateFutureProjection;

function showProjectionResults(projection) {
    const results = document.getElementById('future-results');
    const analysis = projection.analysis || {};
    const currentState = projection.current_state || {};
    const projectedState = projection.projected_state || {};
    const portfolioProjection = analysis.portfolio_projection || {};

    // Calculate projected values
    const currentValue = currentState.total_value || 0;
    const lastYearKey = `year_${projection.years}`;
    const lastYearProjection = portfolioProjection[lastYearKey] || { pessimistic: 0, base: 0, optimistic: 0 };

    const formatMoney = n => '$' + Math.abs(n).toLocaleString('en-US', { maximumFractionDigits: 0 });
    const formatPct = n => (n >= 0 ? '+' : '') + n.toFixed(1) + '%';

    // Build ticker analysis HTML
    const tickerAnalyses = Object.entries(analysis.ticker_analysis || {}).map(([ticker, ta]) => {
        const rates = ta.annual_growth_rates || {};
        const catalysts = ta.current_catalysts || [];
        const confidence = ta.confidence || 'low';

        return `
            <div class="ticker-analysis">
                <h4>
                    ${ticker}
                    <span class="confidence ${confidence}">${confidence.toUpperCase()}</span>
                </h4>
                <div class="ticker-growth-rates">
                    <span style="color: #ff4444;">📉 ${formatPct(rates.pessimistic || 0)}</span>
                    <span style="color: #627eea;">📊 ${formatPct(rates.base || 0)}</span>
                    <span style="color: #00ff88;">📈 ${formatPct(rates.optimistic || 0)}</span>
                </div>
                <p style="margin: 8px 0; font-size: 13px; opacity: 0.8;">${ta.industry_trend || 'N/A'}</p>
                ${catalysts.length > 0 ? `
                    <div class="ticker-catalysts">
                        <strong>Catalysts:</strong>
                        <ul>${catalysts.map(c => `<li>${c}</li>`).join('')}</ul>
                    </div>
                ` : ''}
            </div>
        `;
    }).join('');

    // Build timeline bars
    const frames = projection.frames || [];
    const maxValue = Math.max(...frames.map(f => f.total_value));
    const minValue = Math.min(...frames.map(f => f.total_value));
    const valueRange = maxValue - minValue || 1;
    const sampleSize = Math.min(12, frames.length); // Show up to 12 bars
    const step = Math.max(1, Math.floor(frames.length / sampleSize));
    const sampledFrames = frames.filter((_, i) => i % step === 0 || i === frames.length - 1);

    const timelineBars = sampledFrames.map((frame, i) => {
        const height = ((frame.total_value - minValue) / valueRange) * 180 + 10;
        const width = 100 / sampledFrames.length - 1;
        const left = i * (100 / sampledFrames.length);
        return `<div class="timeline-bar" style="left: ${left}%; width: ${width}%; height: ${height}px;" title="${formatMoney(frame.total_value)} - ${frame.date}"></div>`;
    }).join('');

    const timelineLabels = sampledFrames.filter((_, i) => i % 3 === 0 || i === sampledFrames.length - 1).map(f => f.date.substring(0, 7)).join('</span><span>');

    // Build macro outlook
    const macro = analysis.macro_outlook || {};

    results.innerHTML = `
        <div class="projection-result">
            <div class="projection-summary">
                <h3>📊 ${projection.years}-Year Portfolio Projection</h3>
                <p style="opacity: 0.7; margin-bottom: 15px;">Starting value: ${formatMoney(currentValue)} | Source: ${analysis.source || 'statistical'}</p>
                <div class="projection-scenarios">
                    <div class="scenario-card pessimistic">
                        <h4>Pessimistic</h4>
                        <div class="value">${formatMoney(currentValue * (1 + lastYearProjection.pessimistic / 100))}</div>
                        <p style="font-size: 12px; opacity: 0.7; margin-top: 5px;">${formatPct(lastYearProjection.pessimistic)}</p>
                    </div>
                    <div class="scenario-card base">
                        <h4>Base Case</h4>
                        <div class="value">${formatMoney(currentValue * (1 + lastYearProjection.base / 100))}</div>
                        <p style="font-size: 12px; opacity: 0.7; margin-top: 5px;">${formatPct(lastYearProjection.base)}</p>
                    </div>
                    <div class="scenario-card optimistic">
                        <h4>Optimistic</h4>
                        <div class="value">${formatMoney(currentValue * (1 + lastYearProjection.optimistic / 100))}</div>
                        <p style="font-size: 12px; opacity: 0.7; margin-top: 5px;">${formatPct(lastYearProjection.optimistic)}</p>
                    </div>
                </div>
            </div>

            <div class="projection-timeline">
                <h3>📈 Value Timeline (Base Case)</h3>
                <div class="timeline-chart">
                    ${timelineBars}
                </div>
                <div class="timeline-labels">
                    <span>${timelineLabels}</span>
                </div>
            </div>

            <div class="projection-analysis">
                <h3>🌍 Macro Outlook</h3>
                <div class="macro-outlook">
                    <div class="macro-item">
                        <label>Summary</label>
                        <span>${macro.summary || 'N/A'}</span>
                    </div>
                    <div class="macro-item">
                        <label>Interest Rates</label>
                        <span>${macro.interest_rates || 'N/A'}</span>
                    </div>
                    <div class="macro-item">
                        <label>Inflation</label>
                        <span>${macro.inflation || 'N/A'}</span>
                    </div>
                    <div class="macro-item">
                        <label>GDP Growth</label>
                        <span>${macro.gdp_growth || 'N/A'}</span>
                    </div>
                </div>
            </div>

            <div class="projection-analysis">
                <h3>📊 Ticker Analysis</h3>
                <div class="ticker-analyses">
                    ${tickerAnalyses || '<p style="opacity: 0.6;">No ticker analysis available</p>'}
                </div>
            </div>
        </div>
    `;
}

async function viewProjection(projectionId) {
    try {
        const response = await fetch(`/api/alt-history/projections/${projectionId}`);
        const data = await response.json();

        if (data.error) {
            alert('Error loading projection: ' + data.error);
            return;
        }

        showProjectionResults(data);
    } catch (error) {
        console.error('Failed to load projection:', error);
        alert('Failed to load projection');
    }
}
window.viewProjection = viewProjection;

async function deleteProjection(projectionId) {
    if (!confirm('Delete this projection? This cannot be undone.')) return;

    try {
        await fetch(`/api/alt-history/projections/${projectionId}`, { method: 'DELETE' });
        loadSavedProjections();
        document.getElementById('future-results').innerHTML = '';
    } catch (error) {
        console.error('Failed to delete projection:', error);
    }
}
window.deleteProjection = deleteProjection;

// ============ End Future Projection Functions ============

// ============ Cluster View Functions ============

async function enterClusterView() {
    closeAltRealityModal();

    // Show loading
    showClusterLoading(true);

    try {
        // Load all projections data
        await loadClusterData();

        if (clusterSystems.length === 0) {
            alert('No projections found. Generate some future projections first!');
            showClusterLoading(false);
            return;
        }

        clusterViewActive = true;

        // Hide main solar system
        hideMainSystem();

        // Create cluster UI overlay
        createClusterUI();

        // Create mini solar systems for each projection
        clusterSystems.forEach((sys, index) => {
            createMiniSolarSystem(sys, index);
        });

        // Position systems in cluster formation
        positionClusterSystems();

        // Move camera to view cluster
        const clusterCameraPos = new THREE.Vector3(0, 60, 100);
        gsap.to(camera.position, {
            x: clusterCameraPos.x,
            y: clusterCameraPos.y,
            z: clusterCameraPos.z,
            duration: 1.5,
            ease: "power2.inOut"
        });
        controls.target.set(0, 0, 0);
        controls.maxDistance = 200;
        controls.minDistance = 30;

        // Initial timeline update
        updateClusterTimeline(0);

    } catch (error) {
        console.error('Failed to enter cluster view:', error);
        alert('Failed to load cluster view: ' + error.message);
    }

    showClusterLoading(false);
}
window.enterClusterView = enterClusterView;

function exitClusterView() {
    clusterViewActive = false;

    // Stop any playback
    clusterPlaybackActive = false;

    // Remove cluster systems from scene
    clusterSystems.forEach(sys => {
        // Remove label
        if (sys.group?.userData?.labelDiv) {
            sys.group.userData.labelDiv.remove();
        }
        if (sys.group) {
            scene.remove(sys.group);
            // Dispose geometries and materials
            sys.group.traverse(obj => {
                if (obj.geometry) obj.geometry.dispose();
                if (obj.material) {
                    if (Array.isArray(obj.material)) {
                        obj.material.forEach(m => m.dispose());
                    } else {
                        obj.material.dispose();
                    }
                }
            });
        }
    });
    clusterSystems = [];

    // Remove cluster UI elements
    const clusterUI = document.getElementById('cluster-ui');
    if (clusterUI) clusterUI.remove();

    // Remove info panel if open
    const infoPanel = document.getElementById('cluster-system-info');
    if (infoPanel) infoPanel.remove();

    // Remove any lingering cluster labels
    document.querySelectorAll('.cluster-system-label').forEach(el => el.remove());

    // Show main system again
    showMainSystem();

    // Reset camera
    gsap.to(camera.position, {
        x: DEFAULT_CAMERA_POS.x,
        y: DEFAULT_CAMERA_POS.y,
        z: DEFAULT_CAMERA_POS.z,
        duration: 1.5,
        ease: "power2.inOut"
    });
    controls.target.set(0, 0, 0);
    controls.maxDistance = 80;
    controls.minDistance = 15;
}
window.exitClusterView = exitClusterView;

function showClusterLoading(show) {
    let loader = document.getElementById('cluster-loading');
    if (show) {
        if (!loader) {
            loader = document.createElement('div');
            loader.id = 'cluster-loading';
            loader.innerHTML = `
                <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                     background: rgba(0,0,0,0.8); display: flex; align-items: center;
                     justify-content: center; z-index: 2000; flex-direction: column;">
                    <div class="loading-spinner" style="width: 60px; height: 60px; border-width: 4px;"></div>
                    <p style="color: white; margin-top: 20px; font-size: 18px;">Loading Cluster View...</p>
                </div>
            `;
            document.body.appendChild(loader);
        }
    } else if (loader) {
        loader.remove();
    }
}

async function loadClusterData() {
    clusterSystems = [];

    // Load reality projection first
    const realityProjection = await generateOrLoadProjection('reality');
    console.log('Reality projection:', realityProjection);

    if (realityProjection && realityProjection.frames?.length > 0) {
        // Validate frames have data
        const firstFrame = realityProjection.frames[0];
        console.log('Reality first frame:', firstFrame);

        clusterSystems.push({
            id: 'reality',
            name: 'Reality',
            projection: realityProjection,
            frames: realityProjection.frames,
            group: null,
            isReality: true,
            modifications: []
        });
        clusterMaxMonths = realityProjection.frames.length;
    }

    // Load alternate history projections
    const altResponse = await fetch('/api/alt-history');
    const altData = await altResponse.json();
    console.log('Alternate histories:', altData);

    for (const history of (altData.histories || [])) {
        const projection = await generateOrLoadProjection(history.id);
        console.log(`Alternate ${history.name} projection:`, projection);

        if (projection && projection.frames?.length > 0) {
            clusterSystems.push({
                id: history.id,
                name: history.name,
                projection: projection,
                frames: projection.frames,
                group: null,
                isReality: false,
                modifications: history.modifications || []
            });
        }
    }

    console.log('Loaded cluster systems:', clusterSystems.length);
}

async function generateOrLoadProjection(historyId) {
    try {
        // Try to generate a new projection (or use cached if exists)
        const response = await fetch('/api/alt-history/projections/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                history_id: historyId,
                years: 3,
                use_llm: false  // Use statistical for speed
            })
        });

        if (!response.ok) return null;
        return await response.json();
    } catch (error) {
        console.error(`Failed to load projection for ${historyId}:`, error);
        return null;
    }
}

function createClusterUI() {
    const ui = document.createElement('div');
    ui.id = 'cluster-ui';
    ui.innerHTML = `
        <style>
            #cluster-ui {
                position: fixed;
                bottom: 0;
                left: 0;
                right: 0;
                z-index: 1000;
                pointer-events: none;
            }
            .cluster-controls {
                background: linear-gradient(to top, rgba(0,0,0,0.9), transparent);
                padding: 30px 20px 20px;
                pointer-events: auto;
            }
            .cluster-timeline {
                display: flex;
                align-items: center;
                gap: 15px;
                margin-bottom: 15px;
            }
            .cluster-timeline label {
                color: #627eea;
                font-weight: bold;
                min-width: 80px;
            }
            .cluster-timeline input[type="range"] {
                flex: 1;
                height: 8px;
                -webkit-appearance: none;
                background: linear-gradient(to right, #627eea, #9c27b0);
                border-radius: 4px;
                cursor: pointer;
            }
            .cluster-timeline input[type="range"]::-webkit-slider-thumb {
                -webkit-appearance: none;
                width: 20px;
                height: 20px;
                background: white;
                border-radius: 50%;
                cursor: pointer;
                box-shadow: 0 0 10px rgba(98, 126, 234, 0.5);
            }
            .cluster-date {
                color: white;
                font-size: 14px;
                min-width: 100px;
                text-align: right;
            }
            .cluster-exit {
                position: fixed;
                top: 20px;
                right: 20px;
                background: rgba(255,68,68,0.8);
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                cursor: pointer;
                font-size: 14px;
                pointer-events: auto;
                transition: background 0.2s;
            }
            .cluster-exit:hover { background: rgba(255,68,68,1); }

            .cluster-leaderboard {
                position: fixed;
                top: 20px;
                left: 20px;
                background: rgba(0,0,0,0.85);
                border: 1px solid #627eea44;
                border-radius: 12px;
                padding: 15px;
                min-width: 250px;
                pointer-events: auto;
            }
            .cluster-leaderboard h3 {
                margin: 0 0 10px 0;
                color: #627eea;
                font-size: 14px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            .leaderboard-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 8px 0;
                border-bottom: 1px solid #ffffff11;
            }
            .leaderboard-item:last-child { border-bottom: none; }
            .leaderboard-rank {
                width: 24px;
                height: 24px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: bold;
                font-size: 12px;
                margin-right: 10px;
            }
            .leaderboard-rank.gold { background: linear-gradient(135deg, #ffd700, #ffaa00); color: #333; }
            .leaderboard-rank.silver { background: linear-gradient(135deg, #c0c0c0, #888); color: #333; }
            .leaderboard-rank.bronze { background: linear-gradient(135deg, #cd7f32, #8b4513); color: white; }
            .leaderboard-rank.other { background: #ffffff22; color: white; }
            .leaderboard-name { flex: 1; color: white; font-size: 13px; }
            .leaderboard-name.reality { color: #627eea; font-weight: bold; }
            .leaderboard-value { color: #00ff88; font-weight: bold; font-size: 13px; }
            .leaderboard-value.negative { color: #ff4444; }

            .cluster-play-controls {
                display: flex;
                gap: 10px;
                align-items: center;
            }
            .cluster-play-btn {
                background: #627eea;
                color: white;
                border: none;
                width: 40px;
                height: 40px;
                border-radius: 50%;
                cursor: pointer;
                font-size: 16px;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .cluster-play-btn:hover { background: #7c93ed; }
            .cluster-speed {
                color: white;
                font-size: 12px;
                opacity: 0.7;
            }
        </style>

        <button class="cluster-exit" onclick="exitClusterView()">✕ Exit Cluster View</button>

        <div class="cluster-leaderboard">
            <h3>🏆 Timeline Leaderboard</h3>
            <div id="leaderboard-items">Loading...</div>
        </div>

        <div class="cluster-controls">
            <div class="cluster-timeline">
                <label>Timeline</label>
                <div class="cluster-play-controls">
                    <button class="cluster-play-btn" id="cluster-play-btn" onclick="toggleClusterPlayback()">▶</button>
                    <span class="cluster-speed" id="cluster-speed">1x</span>
                </div>
                <input type="range" id="cluster-timeline-slider" min="0" max="100" value="0"
                       oninput="onClusterTimelineChange(this.value)">
                <span class="cluster-date" id="cluster-date">Now</span>
            </div>
        </div>
    `;
    document.body.appendChild(ui);

    // Initialize leaderboard
    updateClusterLeaderboard();
}

let clusterPlaybackActive = false;
let clusterPlaybackSpeed = 1;

function toggleClusterPlayback() {
    clusterPlaybackActive = !clusterPlaybackActive;
    const btn = document.getElementById('cluster-play-btn');
    btn.textContent = clusterPlaybackActive ? '⏸' : '▶';
}
window.toggleClusterPlayback = toggleClusterPlayback;

function onClusterTimelineChange(value) {
    clusterTimelinePosition = value / 100;
    console.log('Timeline slider changed to:', clusterTimelinePosition);
    updateClusterTimeline(clusterTimelinePosition);
}
window.onClusterTimelineChange = onClusterTimelineChange;

function createMiniSolarSystem(systemData, index) {
    const group = new THREE.Group();
    group.userData = { systemId: systemData.id, systemName: systemData.name };

    // Create mini sun
    const sunGeometry = new THREE.SphereGeometry(1.5, 32, 32);
    const sunMaterial = new THREE.MeshBasicMaterial({
        color: systemData.isReality ? 0xffd700 : 0x627eea,
        transparent: true,
        opacity: 0.9
    });
    const miniSun = new THREE.Mesh(sunGeometry, sunMaterial);

    // Sun glow
    const glowGeometry = new THREE.SphereGeometry(2, 32, 32);
    const glowMaterial = new THREE.MeshBasicMaterial({
        color: systemData.isReality ? 0xffaa00 : 0x9c27b0,
        transparent: true,
        opacity: 0.3,
        side: THREE.BackSide
    });
    const sunGlow = new THREE.Mesh(glowGeometry, glowMaterial);
    miniSun.add(sunGlow);

    group.add(miniSun);
    group.userData.sun = miniSun;
    group.userData.planets = [];

    // Create label
    const labelDiv = document.createElement('div');
    labelDiv.className = 'cluster-system-label';
    labelDiv.style.cssText = `
        position: absolute;
        color: white;
        font-size: 12px;
        font-weight: bold;
        text-align: center;
        text-shadow: 0 0 10px black;
        pointer-events: none;
        white-space: nowrap;
    `;
    labelDiv.textContent = systemData.name;
    group.userData.labelDiv = labelDiv;
    document.body.appendChild(labelDiv);

    // Get initial frame data to create planets
    const initialFrame = systemData.frames[0];
    if (initialFrame && initialFrame.holdings) {
        const totalValue = initialFrame.total_value || 1;
        initialFrame.holdings.forEach((holding, i) => {
            const planet = createMiniPlanet(holding, i, initialFrame.holdings.length, totalValue);
            group.add(planet);
            group.userData.planets.push(planet);
        });
    }

    systemData.group = group;
    scene.add(group);
}

function createMiniPlanet(holding, index, total, totalValue) {
    const { ticker, value, price, shares } = holding;

    // Scale down for mini system
    const sizeRatio = value / totalValue;
    const radius = 0.2 + sizeRatio * 2;

    // Orbit distance based on index
    const orbitDistance = 4 + index * 2;
    const angle = (index / total) * Math.PI * 2;

    // Planet colors
    const tickerColors = {
        BMNR: 0x8B4513, NBIS: 0x4169E1, TSLA: 0xC0C0C0,
        META: 0x1877F2, RKLB: 0x9400D3, PLTR: 0x00CED1
    };
    const color = tickerColors[ticker] || 0x888888;

    const geometry = new THREE.SphereGeometry(radius, 16, 16);
    const material = new THREE.MeshBasicMaterial({
        color: color,
        transparent: true,
        opacity: 0.8
    });
    const planet = new THREE.Mesh(geometry, material);

    planet.position.x = Math.cos(angle) * orbitDistance;
    planet.position.z = Math.sin(angle) * orbitDistance;

    planet.userData = { ticker, orbitDistance, orbitAngle: angle, orbitSpeed: 0.3 + Math.random() * 0.2 };

    return planet;
}

function positionClusterSystems() {
    const count = clusterSystems.length;
    if (count === 0) return;

    // Arrange in a circle or grid formation
    const radius = count <= 4 ? 25 : 20 + count * 3;

    clusterSystems.forEach((sys, index) => {
        if (!sys.group) return;

        if (count === 1) {
            sys.group.position.set(0, 0, 0);
        } else {
            const angle = (index / count) * Math.PI * 2 - Math.PI / 2;
            sys.group.position.x = Math.cos(angle) * radius;
            sys.group.position.z = Math.sin(angle) * radius;
            sys.group.position.y = 0;
        }
    });
}

function updateClusterTimeline(position) {
    clusterTimelinePosition = position;

    // PASS 1: Calculate all growth values first
    clusterSystems.forEach(sys => {
        if (sys.frames && sys.frames.length > 0) {
            const frameIndex = Math.floor(position * (sys.frames.length - 1));
            const frame = sys.frames[frameIndex];

            if (frame) {
                const initialValue = sys.frames[0]?.total_value || 1;
                const currentValue = frame.total_value || initialValue;
                sys.currentValue = currentValue;
                sys.growthPercent = ((currentValue / initialValue) - 1) * 100;
            }
        }
    });

    // Calculate relative differences for EXTREME visualization
    const growths = clusterSystems.filter(s => s.growthPercent !== undefined).map(s => s.growthPercent);
    const minGrowth = Math.min(...growths);
    const maxGrowth = Math.max(...growths);
    const avgGrowth = growths.reduce((a, b) => a + b, 0) / growths.length;
    const growthRange = maxGrowth - minGrowth || 1;

    // PASS 2: Update visuals with EXTREME RELATIVE scaling
    clusterSystems.forEach(sys => {
        if (!sys.group || sys.growthPercent === undefined) return;

        // Calculate relative performance (0 = worst, 1 = best)
        const relativePerformance = (sys.growthPercent - minGrowth) / growthRange;

        // Apply power curve to EXAGGERATE small differences
        // relativePerf 0.5 becomes 0.25, making differences more visible
        const exaggeratedPerf = Math.pow(relativePerformance, 0.5); // sqrt makes middle values lower
        // Then apply another curve to spread out the top performers
        const amplifiedPerf = relativePerformance < 0.5
            ? relativePerformance * 0.3  // Losers get crushed down
            : 0.15 + (relativePerformance - 0.5) * 1.7; // Winners get boosted up

        // EXTREME scaling: worst = 0.15x, best = 4x
        const systemScale = 0.15 + amplifiedPerf * 3.85;

        // Scale the entire system group
        sys.group.scale.setScalar(systemScale);

        // Update sun color/glow based on relative performance
        if (sys.group.userData.sun) {
            const sun = sys.group.userData.sun;
            const glow = sun.children[0]; // The glow mesh

            // Winner gets MUCH brighter, loser almost disappears
            const opacity = 0.15 + amplifiedPerf * 0.85;
            sun.material.opacity = opacity;

            // Emissive intensity for glow effect
            if (sun.material.emissiveIntensity !== undefined) {
                sun.material.emissiveIntensity = amplifiedPerf * 2;
            }

            // Color shift: deep red (loser) -> bright green (winner)
            if (!sys.isReality) {
                const hue = relativePerformance * 0.35; // 0=red, 0.35=green
                const saturation = 0.7 + relativePerformance * 0.3;
                const lightness = 0.25 + amplifiedPerf * 0.5;
                sun.material.color.setHSL(hue, saturation, lightness);
                if (glow) {
                    glow.material.color.setHSL(hue, saturation * 0.8, lightness * 0.8);
                    glow.material.opacity = 0.1 + amplifiedPerf * 0.6;
                    // Scale glow based on performance
                    glow.scale.setScalar(1 + amplifiedPerf * 1.5);
                }
            } else {
                // Reality: gold that intensifies with performance
                const lightness = 0.3 + amplifiedPerf * 0.4;
                sun.material.color.setHSL(0.12, 0.95, lightness);
                if (glow) {
                    glow.material.opacity = 0.2 + amplifiedPerf * 0.5;
                    glow.scale.setScalar(1 + amplifiedPerf * 1.2);
                }
            }
        }

        // Adjust Y position: winners float up, losers sink down
        const yOffset = (relativePerformance - 0.5) * 15;
        sys.group.position.y = yOffset;

        // Update planets based on holdings
        const frameIndex = Math.floor(position * (sys.frames.length - 1));
        const frame = sys.frames[frameIndex];
        const planets = sys.group.userData.planets || [];
        const holdings = frame?.holdings || [];

        planets.forEach((planet, i) => {
            if (holdings[i]) {
                const holding = holdings[i];
                const initialHolding = sys.frames[0]?.holdings?.[i];
                if (initialHolding && initialHolding.value > 0) {
                    const holdingGrowth = holding.value / initialHolding.value;
                    // Planet scale relative to BOTH its growth AND system performance
                    const planetScale = (0.2 + holdingGrowth * 0.8) * (0.5 + amplifiedPerf);
                    planet.scale.setScalar(Math.max(0.1, Math.min(4, planetScale)));

                    // Planets fade with poor performance
                    if (planet.material) {
                        planet.material.opacity = 0.3 + amplifiedPerf * 0.7;
                    }
                }
            }
        });

        // Update label size/opacity to match
        if (sys.group.userData.labelDiv) {
            const label = sys.group.userData.labelDiv;
            label.style.opacity = 0.3 + amplifiedPerf * 0.7;
            label.style.fontSize = `${10 + amplifiedPerf * 8}px`;
        }

        // Debug logging at key positions
        if (position === 0 || position > 0.99) {
            console.log(`${sys.name}: growth=${sys.growthPercent.toFixed(1)}%, relative=${relativePerformance.toFixed(2)}, amplified=${amplifiedPerf.toFixed(2)}, scale=${systemScale.toFixed(2)}`);
        }
    });

    // Update date display
    const dateEl = document.getElementById('cluster-date');
    if (dateEl && clusterSystems[0]?.frames) {
        const frameIndex = Math.floor(position * (clusterSystems[0].frames.length - 1));
        const frame = clusterSystems[0].frames[frameIndex];
        if (frame?.date) {
            dateEl.textContent = frame.date;
        }
    }

    // Update slider
    const slider = document.getElementById('cluster-timeline-slider');
    if (slider) {
        slider.value = position * 100;
    }

    // Update leaderboard
    updateClusterLeaderboard();
}

function updateClusterLeaderboard() {
    const container = document.getElementById('leaderboard-items');
    if (!container) {
        console.log('Leaderboard container not found!');
        return;
    }

    // Sort systems by current value
    const sorted = [...clusterSystems]
        .filter(s => s.currentValue !== undefined && s.currentValue > 0)
        .sort((a, b) => b.currentValue - a.currentValue);

    console.log('Leaderboard update: sorted systems=', sorted.length, 'values=', sorted.map(s => `${s.name}:${s.growthPercent?.toFixed(1)}%`));

    if (sorted.length === 0) {
        container.innerHTML = '<p style="color: #666; font-size: 12px;">Move timeline to see rankings</p>';
        return;
    }

    container.innerHTML = sorted.map((sys, index) => {
        const rankClass = index === 0 ? 'gold' : index === 1 ? 'silver' : index === 2 ? 'bronze' : 'other';
        const nameClass = sys.isReality ? 'reality' : '';
        const valueClass = sys.growthPercent >= 0 ? '' : 'negative';
        const growthSign = sys.growthPercent >= 0 ? '+' : '';
        const valueStr = sys.currentValue > 1000000
            ? `$${(sys.currentValue/1000000).toFixed(2)}M`
            : `$${(sys.currentValue/1000).toFixed(0)}K`;

        return `
            <div class="leaderboard-item">
                <span class="leaderboard-rank ${rankClass}">${index + 1}</span>
                <span class="leaderboard-name ${nameClass}">${sys.name}</span>
                <span class="leaderboard-value ${valueClass}">${valueStr} (${growthSign}${sys.growthPercent?.toFixed(1) || 0}%)</span>
            </div>
        `;
    }).join('');
}

function hideMainSystem() {
    // Hide sun and planets
    if (sun) sun.visible = false;
    planets.forEach(planet => {
        if (planet.group) planet.group.visible = false;
    });
    // Hide pyramid
    const pyramid = scene.getObjectByName('alternatePyramid');
    if (pyramid) pyramid.visible = false;
    // Hide cash planet
    const cashPlanet = scene.getObjectByName('cashPlanet');
    if (cashPlanet) cashPlanet.visible = false;
}

function showMainSystem() {
    if (sun) sun.visible = true;
    planets.forEach(planet => {
        if (planet.group) planet.group.visible = true;
    });
    const pyramid = scene.getObjectByName('alternatePyramid');
    if (pyramid) pyramid.visible = true;
    const cashPlanet = scene.getObjectByName('cashPlanet');
    if (cashPlanet) cashPlanet.visible = true;
}

// Update cluster view in animation loop
function updateClusterView(deltaTime) {
    if (!clusterViewActive) return;

    // Animate planets orbiting
    clusterSystems.forEach(sys => {
        if (!sys.group) return;

        const planets = sys.group.userData.planets || [];
        planets.forEach(planet => {
            if (planet.userData.orbitDistance) {
                planet.userData.orbitAngle += planet.userData.orbitSpeed * deltaTime * 0.5;
                planet.position.x = Math.cos(planet.userData.orbitAngle) * planet.userData.orbitDistance;
                planet.position.z = Math.sin(planet.userData.orbitAngle) * planet.userData.orbitDistance;
            }
        });

        // Update label position
        if (sys.group.userData.labelDiv) {
            const pos = sys.group.position.clone();
            pos.y += 8;
            pos.project(camera);
            const x = (pos.x * 0.5 + 0.5) * window.innerWidth;
            const y = (-pos.y * 0.5 + 0.5) * window.innerHeight;
            sys.group.userData.labelDiv.style.left = x + 'px';
            sys.group.userData.labelDiv.style.top = y + 'px';
            sys.group.userData.labelDiv.style.transform = 'translate(-50%, -50%)';
        }
    });

    // Auto-play if active
    if (clusterPlaybackActive) {
        const speed = 0.0005 * clusterPlaybackSpeed;
        clusterTimelinePosition = Math.min(1, clusterTimelinePosition + speed);
        updateClusterTimeline(clusterTimelinePosition);

        if (clusterTimelinePosition >= 1) {
            clusterPlaybackActive = false;
            document.getElementById('cluster-play-btn').textContent = '▶';
        }
    }
}

// Handle clicks in cluster view
function onClusterClick(event) {
    if (!clusterViewActive) return;

    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);

    // Check each system's sun for intersection
    for (const sys of clusterSystems) {
        if (!sys.group?.userData?.sun) continue;

        const intersects = raycaster.intersectObject(sys.group.userData.sun, true);
        if (intersects.length > 0) {
            showClusterSystemInfo(sys);
            return;
        }
    }

    // Click on empty space closes any open info panel
    closeClusterSystemInfo();
}

function showClusterSystemInfo(sys) {
    // Close existing
    closeClusterSystemInfo();

    // Analyze major lifecycle events
    const lifecycleEvents = analyzeLifecycleEvents(sys);

    // Get history details if it's an alternate
    const modifications = sys.projection?.analysis?.ticker_analysis ?
        Object.keys(sys.projection.analysis.ticker_analysis).slice(0, 3) : [];

    const description = sys.isReality ?
        'Your actual portfolio - the ground truth against which all alternates are compared.' :
        (sys.projection?.description || getAlternateDescription(sys));

    // Calculate stats
    const startValue = sys.frames[0]?.total_value || 0;
    const endValue = sys.frames[sys.frames.length - 1]?.total_value || 0;
    const totalGrowth = ((endValue / startValue) - 1) * 100;

    const panel = document.createElement('div');
    panel.id = 'cluster-system-info';
    panel.innerHTML = `
        <style>
            #cluster-system-info {
                position: fixed;
                top: 50%;
                right: 20px;
                transform: translateY(-50%);
                width: 320px;
                max-height: 80vh;
                overflow-y: auto;
                background: rgba(0,0,0,0.95);
                border: 1px solid ${sys.isReality ? '#ffd700' : '#627eea'};
                border-radius: 16px;
                padding: 20px;
                z-index: 1001;
                box-shadow: 0 0 30px ${sys.isReality ? 'rgba(255,215,0,0.3)' : 'rgba(98,126,234,0.3)'};
            }
            .csi-header {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                margin-bottom: 15px;
            }
            .csi-header h2 {
                margin: 0;
                color: ${sys.isReality ? '#ffd700' : '#627eea'};
                font-size: 20px;
            }
            .csi-close {
                background: none;
                border: none;
                color: white;
                font-size: 24px;
                cursor: pointer;
                opacity: 0.7;
                padding: 0;
                line-height: 1;
            }
            .csi-close:hover { opacity: 1; }
            .csi-badge {
                display: inline-block;
                padding: 3px 8px;
                border-radius: 4px;
                font-size: 11px;
                margin-top: 5px;
                background: ${sys.isReality ? '#ffd70033' : '#627eea33'};
                color: ${sys.isReality ? '#ffd700' : '#627eea'};
            }
            .csi-description {
                color: #ccc;
                font-size: 13px;
                line-height: 1.5;
                margin-bottom: 20px;
                padding-bottom: 15px;
                border-bottom: 1px solid #ffffff15;
            }
            .csi-stats {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 10px;
                margin-bottom: 20px;
            }
            .csi-stat {
                background: #ffffff08;
                padding: 12px;
                border-radius: 8px;
                text-align: center;
            }
            .csi-stat label {
                display: block;
                font-size: 11px;
                color: #888;
                margin-bottom: 5px;
            }
            .csi-stat value {
                display: block;
                font-size: 18px;
                font-weight: bold;
                color: white;
            }
            .csi-stat value.positive { color: #00ff88; }
            .csi-stat value.negative { color: #ff4444; }
            .csi-section {
                margin-bottom: 15px;
            }
            .csi-section h3 {
                color: #627eea;
                font-size: 13px;
                margin: 0 0 10px 0;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            .csi-lifecycle {
                background: #ffffff08;
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 8px;
            }
            .csi-lifecycle .date {
                font-size: 11px;
                color: #888;
            }
            .csi-lifecycle .event {
                font-size: 13px;
                color: white;
                margin-top: 4px;
            }
            .csi-lifecycle .impact {
                font-size: 12px;
                margin-top: 4px;
            }
            .csi-lifecycle .impact.positive { color: #00ff88; }
            .csi-lifecycle .impact.negative { color: #ff4444; }
            .csi-modifications {
                display: flex;
                flex-wrap: wrap;
                gap: 6px;
            }
            .csi-mod {
                background: #627eea22;
                color: #627eea;
                padding: 4px 10px;
                border-radius: 12px;
                font-size: 11px;
            }
        </style>

        <div class="csi-header">
            <div>
                <h2>${sys.name}</h2>
                <span class="csi-badge">${sys.isReality ? '🌟 Reality' : '🔮 Alternate Timeline'}</span>
            </div>
            <button class="csi-close" onclick="closeClusterSystemInfo()">&times;</button>
        </div>

        <p class="csi-description">${description}</p>

        <div class="csi-stats">
            <div class="csi-stat">
                <label>Starting Value</label>
                <value>$${(startValue / 1000).toFixed(0)}K</value>
            </div>
            <div class="csi-stat">
                <label>Projected Value</label>
                <value>$${(endValue / 1000).toFixed(0)}K</value>
            </div>
            <div class="csi-stat">
                <label>Total Growth</label>
                <value class="${totalGrowth >= 0 ? 'positive' : 'negative'}">${totalGrowth >= 0 ? '+' : ''}${totalGrowth.toFixed(1)}%</value>
            </div>
            <div class="csi-stat">
                <label>Projection</label>
                <value>${sys.projection?.years || 3} Years</value>
            </div>
        </div>

        ${!sys.isReality && sys.projection?.modifications?.length ? `
            <div class="csi-section">
                <h3>📝 Modifications</h3>
                <div class="csi-modifications">
                    ${sys.projection.modifications.map(mod =>
                        `<span class="csi-mod">${formatModification(mod)}</span>`
                    ).join('')}
                </div>
            </div>
        ` : ''}

        <div class="csi-section">
            <h3>📊 Major Lifecycle Events</h3>
            ${lifecycleEvents.map(evt => `
                <div class="csi-lifecycle">
                    <div class="date">${evt.date}</div>
                    <div class="event">${evt.event}</div>
                    <div class="impact ${evt.impact >= 0 ? 'positive' : 'negative'}">
                        ${evt.impact >= 0 ? '📈' : '📉'} ${evt.impact >= 0 ? '+' : ''}${evt.impact.toFixed(1)}% ${evt.reason}
                    </div>
                </div>
            `).join('')}
        </div>
    `;

    document.body.appendChild(panel);
}

function closeClusterSystemInfo() {
    const panel = document.getElementById('cluster-system-info');
    if (panel) panel.remove();
}
window.closeClusterSystemInfo = closeClusterSystemInfo;

function analyzeLifecycleEvents(sys) {
    const events = [];
    const frames = sys.frames || [];

    if (frames.length < 2) return events;

    // Find significant changes (> 5% monthly change)
    let prevValue = frames[0].total_value;

    for (let i = 1; i < frames.length; i++) {
        const frame = frames[i];
        const change = ((frame.total_value / prevValue) - 1) * 100;

        if (Math.abs(change) > 5) {
            // Find which holdings drove the change
            const drivers = findChangeDrivers(frames[i-1], frame);

            events.push({
                date: frame.date,
                event: change > 0 ? 'Portfolio Surge' : 'Portfolio Decline',
                impact: change,
                reason: drivers
            });
        }

        prevValue = frame.total_value;
    }

    // Also add milestone events (first to reach certain thresholds)
    const startValue = frames[0].total_value;
    const milestones = [1.25, 1.5, 2.0]; // 25%, 50%, 100% growth

    for (const milestone of milestones) {
        const targetValue = startValue * milestone;
        const frameIndex = frames.findIndex(f => f.total_value >= targetValue);

        if (frameIndex > 0) {
            const alreadyHas = events.some(e => e.date === frames[frameIndex].date);
            if (!alreadyHas) {
                events.push({
                    date: frames[frameIndex].date,
                    event: `🎯 Reached ${((milestone - 1) * 100).toFixed(0)}% Growth Milestone`,
                    impact: (milestone - 1) * 100,
                    reason: `Portfolio value hit $${(targetValue/1000).toFixed(0)}K`
                });
            }
        }
    }

    // Sort by date and return top 4
    events.sort((a, b) => new Date(a.date) - new Date(b.date));
    return events.slice(0, 4);
}

function findChangeDrivers(prevFrame, currFrame) {
    const prevHoldings = prevFrame.holdings || [];
    const currHoldings = currFrame.holdings || [];

    const changes = [];

    for (const curr of currHoldings) {
        const prev = prevHoldings.find(h => h.ticker === curr.ticker);
        if (prev) {
            const change = ((curr.value / prev.value) - 1) * 100;
            if (Math.abs(change) > 3) {
                changes.push({ ticker: curr.ticker, change });
            }
        }
    }

    // Sort by absolute change
    changes.sort((a, b) => Math.abs(b.change) - Math.abs(a.change));

    if (changes.length === 0) return 'Market movement';

    const top = changes[0];
    return `${top.ticker} ${top.change > 0 ? 'up' : 'down'} ${Math.abs(top.change).toFixed(0)}%`;
}

function formatModification(mod) {
    switch (mod.type) {
        case 'remove_ticker':
            return `No ${mod.ticker}`;
        case 'scale_position':
            return `${mod.scale}x ${mod.ticker}`;
        case 'add_trade':
            return `${mod.action} ${mod.shares} ${mod.ticker}`;
        default:
            return mod.type;
    }
}

function getAlternateDescription(sys) {
    const mods = sys.projection?.modifications || [];
    if (mods.length === 0) return 'An alternate version of your portfolio.';

    const descriptions = mods.map(mod => {
        switch (mod.type) {
            case 'remove_ticker':
                return `never invested in ${mod.ticker}`;
            case 'scale_position':
                return `${mod.scale > 1 ? 'increased' : 'decreased'} ${mod.ticker} position by ${mod.scale}x`;
            case 'add_trade':
                return `${mod.action.toLowerCase()} ${mod.shares} shares of ${mod.ticker}`;
            default:
                return 'made changes to the portfolio';
        }
    });

    return `What if you ${descriptions.join(' and ')}?`;
}

// ============ End Cluster View Functions ============

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

// ==================== CATACLYSM EFFECT ====================
let cataclysmActive = false;
let cataclysmParticles = null;
let shockwaveRing = null;
let originalPlanetStates = new Map();
let cataclysmStartTime = 0;

function triggerCataclysm(message = "RECALIBRATING SYSTEM...") {
    if (cataclysmActive) return;
    cataclysmActive = true;
    cataclysmStartTime = clock.getElapsedTime();

    // Store original planet positions and create explosion vectors
    planets.forEach((data, ticker) => {
        const group = data.group;
        originalPlanetStates.set(ticker, {
            position: group.position.clone(),
            scale: group.scale.clone(),
            rotation: group.rotation.clone()
        });

        // Random explosion direction (outward from center)
        const direction = new THREE.Vector3(
            group.position.x + (Math.random() - 0.5) * 5,
            (Math.random() - 0.5) * 20,
            group.position.z + (Math.random() - 0.5) * 5
        ).normalize();

        group.userData.explosionVelocity = direction.multiplyScalar(15 + Math.random() * 25);
        group.userData.explosionSpin = new THREE.Vector3(
            (Math.random() - 0.5) * 0.3,
            (Math.random() - 0.5) * 0.3,
            (Math.random() - 0.5) * 0.3
        );
    });

    // Make sun explode
    if (sun) {
        gsap.to(sun.scale, {
            x: 3, y: 3, z: 3,
            duration: 0.3,
            yoyo: true,
            repeat: 5,
            ease: "power2.inOut"
        });

        // Intense flash
        gsap.to(sun.material, {
            emissiveIntensity: 5,
            duration: 0.2,
            yoyo: true,
            repeat: 3
        });
    }

    // Create massive explosion particle system
    const particleCount = 3000;
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);
    const velocities = new Float32Array(particleCount * 3);
    const sizes = new Float32Array(particleCount);

    for (let i = 0; i < particleCount; i++) {
        // Start at center (sun position)
        positions[i * 3] = (Math.random() - 0.5) * 2;
        positions[i * 3 + 1] = (Math.random() - 0.5) * 2;
        positions[i * 3 + 2] = (Math.random() - 0.5) * 2;

        // Explosion velocity (outward)
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.random() * Math.PI;
        const speed = 20 + Math.random() * 40;
        velocities[i * 3] = Math.sin(phi) * Math.cos(theta) * speed;
        velocities[i * 3 + 1] = Math.cos(phi) * speed * 0.5;
        velocities[i * 3 + 2] = Math.sin(phi) * Math.sin(theta) * speed;

        // Fire colors: white -> yellow -> orange -> red
        const t = Math.random();
        if (t < 0.2) {
            colors[i * 3] = 1; colors[i * 3 + 1] = 1; colors[i * 3 + 2] = 0.9; // White-yellow
        } else if (t < 0.5) {
            colors[i * 3] = 1; colors[i * 3 + 1] = 0.7; colors[i * 3 + 2] = 0.1; // Yellow-orange
        } else if (t < 0.8) {
            colors[i * 3] = 1; colors[i * 3 + 1] = 0.3; colors[i * 3 + 2] = 0; // Orange
        } else {
            colors[i * 3] = 0.8; colors[i * 3 + 1] = 0.1; colors[i * 3 + 2] = 0; // Red
        }

        sizes[i] = 0.5 + Math.random() * 1.5;
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));
    geometry.userData.velocities = velocities;

    const material = new THREE.PointsMaterial({
        size: 0.8,
        vertexColors: true,
        transparent: true,
        opacity: 1,
        blending: THREE.AdditiveBlending,
        depthWrite: false
    });

    cataclysmParticles = new THREE.Points(geometry, material);
    scene.add(cataclysmParticles);

    // Create expanding shockwave ring
    const ringGeometry = new THREE.RingGeometry(0.1, 1, 64);
    const ringMaterial = new THREE.MeshBasicMaterial({
        color: 0xff6600,
        transparent: true,
        opacity: 0.8,
        side: THREE.DoubleSide,
        blending: THREE.AdditiveBlending
    });
    shockwaveRing = new THREE.Mesh(ringGeometry, ringMaterial);
    shockwaveRing.rotation.x = Math.PI / 2;
    scene.add(shockwaveRing);

    // Show loading message in HUD
    const statusEl = document.getElementById('system-status');
    if (statusEl) {
        statusEl.innerHTML = `<span style="color: #ff4444; animation: blink 0.3s infinite;">${message}</span>`;
    }

    // Add screen shake effect via CSS
    document.getElementById('canvas-container').classList.add('screen-shake');
}

function updateCataclysm(deltaTime) {
    if (!cataclysmActive) return;

    const elapsed = clock.getElapsedTime() - cataclysmStartTime;
    const decay = Math.max(0, 1 - elapsed * 0.1);

    // Update explosion particles
    if (cataclysmParticles) {
        const positions = cataclysmParticles.geometry.attributes.position.array;
        const velocities = cataclysmParticles.geometry.userData.velocities;
        const sizes = cataclysmParticles.geometry.attributes.size.array;

        for (let i = 0; i < positions.length / 3; i++) {
            positions[i * 3] += velocities[i * 3] * deltaTime * decay;
            positions[i * 3 + 1] += velocities[i * 3 + 1] * deltaTime * decay;
            positions[i * 3 + 2] += velocities[i * 3 + 2] * deltaTime * decay;

            // Add gravity pull back toward center
            if (elapsed > 1) {
                positions[i * 3] *= 0.998;
                positions[i * 3 + 1] *= 0.998;
                positions[i * 3 + 2] *= 0.998;
            }

            // Fade and shrink
            sizes[i] *= 0.999;
        }

        cataclysmParticles.geometry.attributes.position.needsUpdate = true;
        cataclysmParticles.geometry.attributes.size.needsUpdate = true;
        cataclysmParticles.material.opacity = Math.max(0.1, decay);
    }

    // Expand shockwave
    if (shockwaveRing) {
        const scale = 1 + elapsed * 30;
        shockwaveRing.scale.set(scale, scale, 1);
        shockwaveRing.material.opacity = Math.max(0, 0.8 - elapsed * 0.15);
    }

    // Fling planets outward with chaotic spin
    planets.forEach((data, ticker) => {
        const group = data.group;
        if (group.userData.explosionVelocity) {
            group.position.add(group.userData.explosionVelocity.clone().multiplyScalar(deltaTime * decay));
            group.rotation.x += group.userData.explosionSpin.x;
            group.rotation.y += group.userData.explosionSpin.y;
            group.rotation.z += group.userData.explosionSpin.z;

            // Slow down spin over time
            group.userData.explosionSpin.multiplyScalar(0.995);
        }
    });
}

function endCataclysm() {
    if (!cataclysmActive) return;

    // Remove screen shake
    document.getElementById('canvas-container').classList.remove('screen-shake');

    // Animate planets back to original positions
    planets.forEach((data, ticker) => {
        const group = data.group;
        const original = originalPlanetStates.get(ticker);

        if (original) {
            gsap.to(group.position, {
                x: original.position.x,
                y: original.position.y,
                z: original.position.z,
                duration: 2,
                ease: "elastic.out(1, 0.5)"
            });

            gsap.to(group.rotation, {
                x: original.rotation.x,
                y: original.rotation.y,
                z: original.rotation.z,
                duration: 1.5,
                ease: "power2.out"
            });

            gsap.to(group.scale, {
                x: original.scale.x,
                y: original.scale.y,
                z: original.scale.z,
                duration: 1,
                ease: "back.out(1.5)"
            });
        }

        delete group.userData.explosionVelocity;
        delete group.userData.explosionSpin;
    });

    // Fade out and remove explosion particles
    if (cataclysmParticles) {
        gsap.to(cataclysmParticles.material, {
            opacity: 0,
            duration: 1,
            onComplete: () => {
                scene.remove(cataclysmParticles);
                cataclysmParticles.geometry.dispose();
                cataclysmParticles.material.dispose();
                cataclysmParticles = null;
            }
        });
    }

    // Fade out shockwave
    if (shockwaveRing) {
        gsap.to(shockwaveRing.material, {
            opacity: 0,
            duration: 0.5,
            onComplete: () => {
                scene.remove(shockwaveRing);
                shockwaveRing.geometry.dispose();
                shockwaveRing.material.dispose();
                shockwaveRing = null;
            }
        });
    }

    // Reset sun
    if (sun) {
        gsap.to(sun.scale, { x: 1, y: 1, z: 1, duration: 1, ease: "elastic.out(1, 0.5)" });
        gsap.to(sun.material, { emissiveIntensity: 0.8, duration: 1 });
    }

    // Clear status
    const statusEl = document.getElementById('system-status');
    if (statusEl) {
        statusEl.innerHTML = '<span style="color: #00ff88;">SYSTEM STABLE</span>';
        setTimeout(() => { statusEl.textContent = ''; }, 2000);
    }

    originalPlanetStates.clear();
    cataclysmActive = false;
}

// Make functions globally available
window.triggerCataclysm = triggerCataclysm;
window.endCataclysm = endCataclysm;

// ==================== AUTO-FIT SOLAR SYSTEM ====================
function autoFitSystem(animate = true) {
    if (planets.size === 0) return;

    // Calculate bounding sphere of all planets
    let maxDistance = 0;
    let center = new THREE.Vector3(0, 0, 0);
    let pointCount = 0;

    planets.forEach((data) => {
        const group = data.group;
        const dist = group.position.length();
        maxDistance = Math.max(maxDistance, dist);
        center.add(group.position);
        pointCount++;
    });

    if (pointCount > 0) {
        center.divideScalar(pointCount);
    }

    // Add padding for planet sizes and some breathing room
    const padding = 1.5;
    const boundingRadius = maxDistance * padding;

    // Calculate camera distance to fit everything
    const fov = camera.fov * (Math.PI / 180);
    const aspect = camera.aspect;
    const distanceToFit = boundingRadius / Math.tan(fov / 2);

    // Position camera at an angle for better 3D view
    const cameraAngle = Math.PI / 6; // 30 degrees elevation
    const targetPos = new THREE.Vector3(
        0,
        distanceToFit * Math.sin(cameraAngle) * 0.6,
        distanceToFit * Math.cos(cameraAngle)
    );

    // Clamp to reasonable bounds
    const minDist = 25;
    const maxDist = 70;
    const finalDist = Math.max(minDist, Math.min(maxDist, targetPos.length()));
    targetPos.normalize().multiplyScalar(finalDist);

    if (animate) {
        gsap.to(camera.position, {
            x: targetPos.x,
            y: targetPos.y,
            z: targetPos.z,
            duration: 1.5,
            ease: "power2.inOut"
        });
        gsap.to(controls.target, {
            x: 0,
            y: 0,
            z: 0,
            duration: 1.5,
            ease: "power2.inOut"
        });
    } else {
        camera.position.copy(targetPos);
        controls.target.set(0, 0, 0);
    }

    controls.update();
}

// Auto-fit on window resize
function onWindowResize() {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);

    // Re-fit system after resize
    if (planets.size > 0 && !cataclysmActive && !clusterViewActive) {
        autoFitSystem(false);
    }
}

window.autoFitSystem = autoFitSystem;

function updatePlanets(deltaTime) {
    // Update cataclysm effect if active
    updateCataclysm(deltaTime);

    // Skip normal orbit updates during cataclysm
    if (cataclysmActive) return;

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

    // Update alternate reality pyramid
    updateAlternateRealityPyramid(deltaTime);

    // Update popup position if a planet is selected
    if (selectedPlanet) {
        updatePopupPosition(selectedPlanet);
    }

    // Update cluster view if active
    updateClusterView(deltaTime);

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

    // Update holdings grid with command deck styling
    const grid = document.getElementById('holdings-grid');
    grid.innerHTML = '';

    // Add Cash card first with breakdown
    if (data.cash_breakdown) {
        const cb = data.cash_breakdown;
        const cashCard = document.createElement('div');
        cashCard.className = 'holding-card cash-card';
        cashCard.innerHTML = `
            <div class="holding-ticker">CASH</div>
            <div class="holding-value">$${cb.total.toLocaleString('en-US', { maximumFractionDigits: 0 })}</div>
            <div style="font-size: 9px; margin-top: 4px; color: #888;">
                <div>Avail: $${cb.available.toLocaleString('en-US', { maximumFractionDigits: 0 })}</div>
            </div>
        `;
        cashCard.onclick = () => focusOnPlanet('CASH');
        grid.appendChild(cashCard);
    }

    data.holdings.forEach(h => {
        const isGain = h.unrealized_gain_pct >= 0;
        const card = document.createElement('div');
        card.className = 'holding-card' + (isGain ? '' : ' loss');
        card.innerHTML = `
            <div class="holding-ticker">${h.ticker}</div>
            <div class="holding-value">$${h.market_value.toLocaleString('en-US', { maximumFractionDigits: 0 })}</div>
            <div class="holding-gain ${isGain ? 'positive' : 'negative'}">
                ${isGain ? '+' : ''}${h.unrealized_gain_pct.toFixed(1)}%
            </div>
            <div class="holding-shares">${h.shares.toLocaleString()} shares</div>
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

    // Handle cluster view clicks separately
    if (clusterViewActive) {
        onClusterClick(event);
        return;
    }

    // Check sun first
    if (sun) {
        const sunIntersects = raycaster.intersectObject(sun);
        if (sunIntersects.length > 0) {
            zoomToSystem();
            return;
        }
    }

    // Check alternate reality pyramid
    if (alternateRealityPyramid) {
        const pyramidIntersects = raycaster.intersectObject(alternateRealityPyramid, true);
        if (pyramidIntersects.length > 0) {
            showAlternateRealityModal();
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

    // Check pyramid hover
    const pyramidHover = alternateRealityPyramid && raycaster.intersectObject(alternateRealityPyramid, true).length > 0;

    // Update cursor
    if (intersects.length > 0 || (sun && raycaster.intersectObject(sun).length > 0) || pyramidHover) {
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

// ==================== INCOME EVENTS MODAL ====================

async function showIncomeEvents(period = 'ytd') {
    const modal = document.getElementById('income-events-modal');
    const title = document.getElementById('income-modal-title');
    const summary = document.getElementById('income-summary');
    const list = document.getElementById('income-events-list');

    // Determine date range
    const now = new Date();
    let startDate, endDate, titleText;

    if (period === 'ytd') {
        startDate = new Date(now.getFullYear(), 0, 1);
        endDate = now;
        titleText = `${now.getFullYear()} Income Events`;
    } else if (period === 'lastyear') {
        startDate = new Date(now.getFullYear() - 1, 0, 1);
        endDate = new Date(now.getFullYear() - 1, 11, 31);
        titleText = `${now.getFullYear() - 1} Income Events`;
    }

    title.textContent = titleText;
    list.innerHTML = '<p class="income-empty">Loading events...</p>';
    modal.style.display = 'flex';

    try {
        // Fetch all events
        const response = await fetch('/api/events?limit=5000');
        const data = await response.json();

        // Filter for income-generating events within date range
        const incomeTypes = ['OPTION_OPEN', 'OPTION_CLOSE', 'OPTION_EXPIRE', 'DIVIDEND', 'TRADE'];
        const incomeEvents = data.events.filter(event => {
            const eventDate = new Date(event.timestamp);
            if (eventDate < startDate || eventDate > endDate) return false;
            if (!incomeTypes.includes(event.event_type)) return false;

            // Only include trades with gains
            if (event.event_type === 'TRADE') {
                const eventData = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
                return eventData.action === 'SELL' && (eventData.gain_loss > 0 || event.cash_delta > 0);
            }

            // Options and dividends always count
            return true;
        });

        // Calculate totals by category
        let optionIncome = 0;
        let dividendIncome = 0;
        let tradeGains = 0;
        let eventCount = 0;

        incomeEvents.forEach(event => {
            const eventData = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;

            if (event.event_type === 'OPTION_OPEN') {
                optionIncome += eventData.total_premium || eventData.premium || 0;
            } else if (event.event_type === 'OPTION_CLOSE' || event.event_type === 'OPTION_EXPIRE') {
                optionIncome += eventData.profit || 0;
            } else if (event.event_type === 'DIVIDEND') {
                dividendIncome += eventData.amount || 0;
            } else if (event.event_type === 'TRADE') {
                tradeGains += eventData.gain_loss || 0;
            }
            eventCount++;
        });

        const totalIncome = optionIncome + dividendIncome + tradeGains;

        // Update summary
        summary.innerHTML = `
            <div class="income-stat">
                <div class="income-stat-value">$${totalIncome.toLocaleString(undefined, {maximumFractionDigits: 0})}</div>
                <div class="income-stat-label">Total Income</div>
            </div>
            <div class="income-stat">
                <div class="income-stat-value">$${optionIncome.toLocaleString(undefined, {maximumFractionDigits: 0})}</div>
                <div class="income-stat-label">Options</div>
            </div>
            <div class="income-stat">
                <div class="income-stat-value">$${dividendIncome.toLocaleString(undefined, {maximumFractionDigits: 0})}</div>
                <div class="income-stat-label">Dividends</div>
            </div>
            <div class="income-stat">
                <div class="income-stat-value">${eventCount}</div>
                <div class="income-stat-label">Events</div>
            </div>
        `;

        // Sort events by date descending
        incomeEvents.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

        // Build event list
        if (incomeEvents.length === 0) {
            list.innerHTML = '<p class="income-empty">No income events found for this period.</p>';
        } else {
            list.innerHTML = incomeEvents.map(event => {
                const eventData = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
                const date = new Date(event.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

                let typeClass, typeLabel, description, amount;

                if (event.event_type === 'OPTION_OPEN') {
                    typeClass = 'option';
                    typeLabel = 'OPTION';
                    const strategy = eventData.strategy || 'option';
                    description = `Opened <span class="ticker">${eventData.ticker}</span> ${strategy} $${eventData.strike}`;
                    amount = eventData.total_premium || eventData.premium || 0;
                } else if (event.event_type === 'OPTION_CLOSE') {
                    typeClass = 'option';
                    typeLabel = 'CLOSE';
                    description = `Closed <span class="ticker">${eventData.ticker || 'option'}</span> position`;
                    amount = eventData.profit || 0;
                } else if (event.event_type === 'OPTION_EXPIRE') {
                    typeClass = 'option';
                    typeLabel = 'EXPIRE';
                    description = `<span class="ticker">${eventData.ticker || 'Option'}</span> expired worthless`;
                    amount = eventData.full_premium || 0;
                } else if (event.event_type === 'DIVIDEND') {
                    typeClass = 'dividend';
                    typeLabel = 'DIVIDEND';
                    description = `<span class="ticker">${eventData.ticker}</span> dividend (${eventData.shares || '?'} shares)`;
                    amount = eventData.amount || 0;
                } else if (event.event_type === 'TRADE') {
                    typeClass = 'trade';
                    typeLabel = 'TRADE';
                    description = `Sold <span class="ticker">${eventData.ticker}</span> (${eventData.shares} shares)`;
                    amount = eventData.gain_loss || 0;
                }

                const amountClass = amount >= 0 ? '' : 'negative';
                const amountStr = amount >= 0 ? `+$${amount.toLocaleString(undefined, {maximumFractionDigits: 0})}` : `-$${Math.abs(amount).toLocaleString(undefined, {maximumFractionDigits: 0})}`;

                return `
                    <div class="income-event">
                        <span class="income-event-date">${date}</span>
                        <span class="income-event-type ${typeClass}">${typeLabel}</span>
                        <span class="income-event-desc">${description}</span>
                        <span class="income-event-amount ${amountClass}">${amountStr}</span>
                    </div>
                `;
            }).join('');
        }

    } catch (error) {
        console.error('Failed to load income events:', error);
        list.innerHTML = '<p class="income-empty">Failed to load events. Please try again.</p>';
    }
}
window.showIncomeEvents = showIncomeEvents;

function closeIncomeModal() {
    document.getElementById('income-events-modal').style.display = 'none';
}
window.closeIncomeModal = closeIncomeModal;

// ==================== TOKEN USAGE TRACKING ====================

async function fetchTokenUsage() {
    try {
        const response = await fetch('/api/chat/usage');
        if (response.ok) {
            const data = await response.json();
            // Update today's token count in status bar
            const todayTokens = data.today?.total_tokens || 0;
            const todayEl = document.getElementById('today-tokens');
            if (todayEl) {
                todayEl.textContent = formatNumber(todayTokens);
            }
            return data;
        }
    } catch (error) {
        console.error('Failed to fetch token usage:', error);
    }
    return null;
}

function formatNumber(num) {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
}

async function showUsagePanel() {
    const modal = document.getElementById('usage-modal');
    const content = document.getElementById('usage-content');
    modal.style.display = 'flex';
    content.innerHTML = '<div class="usage-loading">Loading usage data...</div>';

    try {
        const data = await fetchTokenUsage();
        if (!data) {
            content.innerHTML = '<p style="color: #ff6b6b;">Failed to load usage data</p>';
            return;
        }

        const total = data.total || {};
        const today = data.today || {};
        const byModel = data.by_model || {};
        const byEndpoint = data.by_endpoint || {};
        const recentCalls = data.recent_calls || [];

        let html = `
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
                <div style="background: rgba(0, 136, 255, 0.1); padding: 15px; border-radius: 8px; border: 1px solid rgba(0, 136, 255, 0.3);">
                    <h3 style="color: #00ffff; margin: 0 0 10px 0; font-size: 14px;">TODAY</h3>
                    <div style="font-size: 24px; color: #fff;">${formatNumber(today.total_tokens || 0)}</div>
                    <div style="font-size: 12px; color: #888;">tokens (${today.requests || 0} requests)</div>
                </div>
                <div style="background: rgba(0, 136, 255, 0.1); padding: 15px; border-radius: 8px; border: 1px solid rgba(0, 136, 255, 0.3);">
                    <h3 style="color: #00ffff; margin: 0 0 10px 0; font-size: 14px;">ALL TIME</h3>
                    <div style="font-size: 24px; color: #fff;">${formatNumber(total.total_tokens || 0)}</div>
                    <div style="font-size: 12px; color: #888;">tokens (${total.requests || 0} requests)</div>
                </div>
            </div>

            <div style="margin-bottom: 20px;">
                <h3 style="color: #00ffff; margin: 0 0 10px 0; font-size: 14px;">BY MODEL</h3>
                <div style="background: rgba(0, 0, 0, 0.3); padding: 10px; border-radius: 4px;">
        `;

        for (const [model, stats] of Object.entries(byModel)) {
            html += `
                <div style="display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid rgba(255,255,255,0.1);">
                    <span style="color: #ccc; font-size: 12px;">${model}</span>
                    <span style="color: #fff; font-size: 12px;">${formatNumber(stats.total_tokens)} tokens</span>
                </div>
            `;
        }
        if (Object.keys(byModel).length === 0) {
            html += '<div style="color: #666; font-size: 12px;">No usage data yet</div>';
        }

        html += `
                </div>
            </div>

            <div style="margin-bottom: 20px;">
                <h3 style="color: #00ffff; margin: 0 0 10px 0; font-size: 14px;">BY ENDPOINT</h3>
                <div style="background: rgba(0, 0, 0, 0.3); padding: 10px; border-radius: 4px;">
        `;

        for (const [endpoint, stats] of Object.entries(byEndpoint)) {
            html += `
                <div style="display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid rgba(255,255,255,0.1);">
                    <span style="color: #ccc; font-size: 12px;">${endpoint}</span>
                    <span style="color: #fff; font-size: 12px;">${formatNumber(stats.total_tokens)} tokens (${stats.requests} calls)</span>
                </div>
            `;
        }
        if (Object.keys(byEndpoint).length === 0) {
            html += '<div style="color: #666; font-size: 12px;">No usage data yet</div>';
        }

        html += `
                </div>
            </div>
        `;

        // Recent calls
        if (recentCalls.length > 0) {
            html += `
                <div>
                    <h3 style="color: #00ffff; margin: 0 0 10px 0; font-size: 14px;">RECENT CALLS</h3>
                    <div style="background: rgba(0, 0, 0, 0.3); padding: 10px; border-radius: 4px; max-height: 150px; overflow-y: auto;">
            `;

            for (const call of recentCalls.slice(-10).reverse()) {
                const time = new Date(call.timestamp).toLocaleTimeString();
                const speed = call.tokens_per_sec ? ` (${call.tokens_per_sec} tok/s)` : '';
                html += `
                    <div style="display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid rgba(255,255,255,0.1); font-size: 11px;">
                        <span style="color: #888;">${time}</span>
                        <span style="color: #ccc;">${call.endpoint}</span>
                        <span style="color: #fff;">${call.total_tokens} tokens${speed}</span>
                    </div>
                `;
            }

            html += `
                    </div>
                </div>
            `;
        }

        // Average speed
        if (data.avg_tokens_per_sec > 0) {
            html += `
                <div style="margin-top: 15px; text-align: center; color: #888; font-size: 12px;">
                    Average speed: ${data.avg_tokens_per_sec} tokens/sec
                </div>
            `;
        }

        content.innerHTML = html;

    } catch (error) {
        console.error('Error showing usage panel:', error);
        content.innerHTML = '<p style="color: #ff6b6b;">Error loading usage data</p>';
    }
}
window.showUsagePanel = showUsagePanel;

function closeUsageModal() {
    document.getElementById('usage-modal').style.display = 'none';
}
window.closeUsageModal = closeUsageModal;

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
    const panel = document.getElementById('playback-console');
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

function togglePlaybackExpand() {
    const panel = document.getElementById('playback-console');
    panel.classList.toggle('compact');
}
window.togglePlaybackExpand = togglePlaybackExpand;

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
    const panel = document.getElementById('legend-console');
    const icon = document.getElementById('legend-toggle-icon');
    const body = document.getElementById('legend-body');
    const isMinimized = panel.classList.contains('minimized');

    if (isMinimized) {
        panel.classList.remove('minimized');
        icon.textContent = '−';
        if (body) body.style.display = 'block';
    } else {
        panel.classList.add('minimized');
        icon.textContent = '+';
        if (body) body.style.display = 'none';
    }
}
window.toggleLegend = toggleLegend;

// ==================== AI INSIGHTS FUNCTIONALITY ====================

let insightsMinimized = false;

function toggleInsights() {
    const panel = document.getElementById('insights-console');
    const icon = document.getElementById('insights-toggle-icon');
    const body = document.getElementById('insights-body');
    insightsMinimized = !insightsMinimized;

    if (insightsMinimized) {
        panel.classList.add('minimized');
        icon.textContent = '+';
        if (body) body.style.display = 'none';
    } else {
        panel.classList.remove('minimized');
        icon.textContent = '−';
        if (body) body.style.display = 'block';
    }
}
window.toggleInsights = toggleInsights;

async function fetchInsights() {
    const loadingEl = document.getElementById('insights-loading');
    const listEl = document.getElementById('insights-list');
    const timestampEl = document.getElementById('insights-timestamp');
    const panel = document.getElementById('insights-console');

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
    const panel = document.getElementById('chat-console');
    const icon = document.getElementById('chat-toggle-icon');
    const body = document.getElementById('chat-body');
    const isMinimized = panel.classList.contains('minimized');

    if (isMinimized) {
        panel.classList.remove('minimized');
        icon.textContent = '−';
        if (body) body.style.display = 'block';
        document.getElementById('chat-input').focus();
    } else {
        panel.classList.add('minimized');
        icon.textContent = '+';
        if (body) body.style.display = 'none';
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
    const panel = document.getElementById('settings-console');
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

// Update prices with CATACLYSM effect
async function refreshPrices() {
    try {
        triggerCataclysm("UPDATING MARKET DATA...");

        const response = await fetch('/api/prices/update', { method: 'POST' });
        if (response.ok) {
            // Wait a bit for dramatic effect then reload
            setTimeout(() => {
                endCataclysm();
                setTimeout(() => location.reload(), 1500);
            }, 2000);
        } else {
            endCataclysm();
        }
    } catch (error) {
        console.error('Error updating prices:', error);
        endCataclysm();
    }
}

// Trigger a fun cosmic event for 15 seconds
function triggerCosmicEvent() {
    triggerCataclysm("COSMIC ANOMALY DETECTED!");

    // Automatically end after 15 seconds
    setTimeout(() => {
        endCataclysm();
    }, 15000);
}

// Make functions globally available
window.refreshPrices = refreshPrices;
window.triggerCosmicEvent = triggerCosmicEvent;

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

// ==================== OPTIONS SCANNER ====================

let scannerData = null;

async function openOptionsScanner() {
    const modal = document.getElementById('options-scanner-modal');
    const loading = document.getElementById('scanner-loading');
    const summary = document.getElementById('scanner-summary');
    const results = document.getElementById('scanner-results');
    const analysis = document.getElementById('scanner-analysis');
    const errors = document.getElementById('scanner-errors');

    // Show modal with loading state
    modal.style.display = 'flex';
    loading.style.display = 'block';
    summary.style.display = 'none';
    results.style.display = 'none';
    analysis.style.display = 'none';
    errors.style.display = 'none';

    try {
        const response = await fetch('/api/scanner/recommendations');
        if (!response.ok) throw new Error('Scan failed');

        scannerData = await response.json();
        displayScannerResults(scannerData);
    } catch (error) {
        console.error('Scanner error:', error);
        loading.style.display = 'none';
        results.innerHTML = `
            <div class="scanner-empty">
                <h3>Scan Failed</h3>
                <p>${error.message}</p>
                <p>Make sure the API server is running and you have holdings with optionable stocks.</p>
            </div>
        `;
        results.style.display = 'block';
    }
}
window.openOptionsScanner = openOptionsScanner;

async function runAnalyzedScan() {
    const loading = document.getElementById('scanner-loading');
    const summary = document.getElementById('scanner-summary');
    const results = document.getElementById('scanner-results');
    const analysis = document.getElementById('scanner-analysis');
    const analyzeBtn = document.querySelector('.scanner-analyze-btn');

    // Show loading
    loading.style.display = 'block';
    summary.style.display = 'none';
    results.style.display = 'none';
    analysis.style.display = 'none';
    analyzeBtn.disabled = true;
    analyzeBtn.textContent = 'Analyzing...';

    try {
        const response = await fetch('/api/scanner/recommendations/analyze');
        if (!response.ok) throw new Error('Analysis failed');

        scannerData = await response.json();
        displayScannerResults(scannerData);
    } catch (error) {
        console.error('Scanner analysis error:', error);
        alert('Analysis failed: ' + error.message);
    } finally {
        analyzeBtn.disabled = false;
        analyzeBtn.textContent = 'AI Analyze';
    }
}
window.runAnalyzedScan = runAnalyzedScan;

function displayScannerResults(data) {
    const loading = document.getElementById('scanner-loading');
    const summary = document.getElementById('scanner-summary');
    const results = document.getElementById('scanner-results');
    const resultsList = document.getElementById('scanner-results-list');
    const analysis = document.getElementById('scanner-analysis');
    const analysisText = document.getElementById('scanner-analysis-text');
    const errors = document.getElementById('scanner-errors');

    loading.style.display = 'none';

    // Update summary
    if (data.portfolio_summary) {
        const ps = data.portfolio_summary;
        document.getElementById('scanner-holdings-count').textContent = ps.holdings_scanned;
        document.getElementById('scanner-ytd-income').textContent =
            '$' + (ps.ytd_income || 0).toLocaleString('en-US', { maximumFractionDigits: 0 });
        document.getElementById('scanner-remaining').textContent =
            '$' + (ps.remaining_goal || 0).toLocaleString('en-US', { maximumFractionDigits: 0 });
        document.getElementById('scanner-potential').textContent =
            '$' + (data.potential_income || 0).toLocaleString('en-US', { maximumFractionDigits: 0 });
        summary.style.display = 'grid';
    }

    // Show AI analysis if available
    if (data.analysis && data.analysis.summary) {
        analysisText.textContent = data.analysis.summary;
        analysis.style.display = 'block';
    }

    // Display recommendations
    if (data.recommendations && data.recommendations.length > 0) {
        resultsList.innerHTML = data.recommendations.map(rec => `
            <div class="scanner-rec">
                <div class="scanner-rec-ticker">${rec.ticker}</div>
                <div class="scanner-rec-strategy ${rec.type.toLowerCase()}">${rec.strategy}</div>
                <div class="scanner-rec-details">
                    <div>
                        <span class="strike">$${rec.strike.toFixed(2)}</span>
                        <span class="exp">exp ${rec.expiration} (${rec.dte}d)</span>
                    </div>
                    <div class="metrics">
                        Delta: ${rec.delta.toFixed(2)} |
                        OTM: ${rec.otm_pct.toFixed(1)}% |
                        ${rec.prob_otm ? `Win Rate: ${rec.prob_otm.toFixed(0)}%` : ''}
                    </div>
                </div>
                <div class="scanner-rec-premium">
                    <div class="amount">$${rec.premium_per_contract.toFixed(0)}</div>
                    <div class="yield">${rec.annualized_yield_pct.toFixed(1)}% ann.</div>
                </div>
                <div class="scanner-rec-score">
                    <div class="score-value">${rec.score.toFixed(0)}</div>
                    <div class="score-label">score</div>
                </div>
            </div>
        `).join('');
        results.style.display = 'block';
    } else {
        resultsList.innerHTML = `
            <div class="scanner-empty">
                <h3>No Recommendations Found</h3>
                <p>No suitable options opportunities were found for your current holdings.</p>
                <p>This could be because:</p>
                <ul style="text-align: left; margin-top: 12px;">
                    <li>Your holdings don't have active options chains</li>
                    <li>No options meet the minimum premium threshold</li>
                    <li>Current market conditions don't favor premium selling</li>
                </ul>
            </div>
        `;
        results.style.display = 'block';
    }

    // Show errors if any
    if (data.scan_errors && data.scan_errors.length > 0) {
        errors.innerHTML = `
            <div class="scanner-error-title">Scan Notes</div>
            <div class="scanner-error-list">${data.scan_errors.join('<br>')}</div>
        `;
        errors.style.display = 'block';
    }
}

function closeOptionsScanner() {
    document.getElementById('options-scanner-modal').style.display = 'none';
}
window.closeOptionsScanner = closeOptionsScanner;

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
        // Hide loading, show command deck
        document.getElementById('loading').style.display = 'none';
        document.getElementById('command-deck').style.display = 'block';

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

        // Create the mysterious Alternate Reality pyramid
        createAlternateRealityPyramid();

        // Auto-fit camera to show all planets
        setTimeout(() => autoFitSystem(true), 500);

        // AI insights are now manually triggered via the refresh button
        // (removed auto-fetch to avoid slow page loads with large models)

        // Check AI/MCP status
        checkAIStatus();

        // Fetch token usage for status bar
        fetchTokenUsage();
    } else {
        document.getElementById('loading').innerHTML = `
            <p style="color: #ff4444;">Failed to load portfolio data.</p>
            <p>Make sure the API server is running at localhost:8000</p>
            <button onclick="location.reload()" class="btn" style="margin-top: 16px; pointer-events: auto;">Retry</button>
        `;
    }
}

// ==================== AI/MCP STATUS CHECK ====================
async function checkAIStatus() {
    // Check LLM status
    try {
        const llmResponse = await fetch('/api/config/llm');
        if (llmResponse.ok) {
            const llmData = await llmResponse.json();
            updateStatusIndicator('llm-status', llmData.enabled, llmData.provider + ': ' + (llmData.local_model || llmData.claude_model));
        }
    } catch (e) {
        updateStatusIndicator('llm-status', false, 'LLM unavailable');
    }

    // Check Dexter/MCP status
    try {
        const dexterResponse = await fetch('/api/research/status');
        if (dexterResponse.ok) {
            const dexterData = await dexterResponse.json();
            const mcpAvailable = dexterData.status?.mcp_available || false;
            const mcpName = dexterData.status?.mcp?.name || 'dexter-mcp';
            updateStatusIndicator('mcp-status', mcpAvailable, mcpAvailable ? `${mcpName} connected` : 'MCP offline');
        }
    } catch (e) {
        updateStatusIndicator('mcp-status', false, 'Dexter unavailable');
    }
}

function updateStatusIndicator(elementId, isOnline, tooltip) {
    const el = document.getElementById(elementId);
    if (!el) return;

    const dot = el.querySelector('.status-dot');
    if (dot) {
        dot.classList.remove('online', 'offline', 'error');
        dot.classList.add(isOnline ? 'online' : 'offline');
    }

    if (isOnline) {
        el.classList.add('active');
    } else {
        el.classList.remove('active');
    }

    el.title = tooltip || (isOnline ? 'Connected' : 'Offline');
}

// Periodically refresh AI status (every 30 seconds)
setInterval(checkAIStatus, 30000);

// Start
main();
