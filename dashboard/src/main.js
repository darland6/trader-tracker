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

async function viewAlternateHistory(historyId) {
    try {
        const response = await fetch(`/api/alt-history/${historyId}`);
        const data = await response.json();

        // Show state comparison
        const comparison = await fetch(`/api/alt-history/${historyId}/compare/reality`).then(r => r.json());
        showComparisonResults(comparison);
        showAltTab('compare');
    } catch (error) {
        console.error('Failed to view history:', error);
    }
}
window.viewAlternateHistory = viewAlternateHistory;

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

    const formatMoney = n => '$' + Math.abs(n).toLocaleString('en-US', { maximumFractionDigits: 0 });
    const diffClass = n => n >= 0 ? 'positive' : 'negative';
    const diffSign = n => n >= 0 ? '+' : '-';

    container.innerHTML = `
        <div class="compare-card">
            <h3>Portfolio Value</h3>
            <div class="compare-row">
                <span>${h1.name}</span>
                <span>${formatMoney(h1.total_value)}</span>
            </div>
            <div class="compare-row">
                <span>${h2.name}</span>
                <span>${formatMoney(h2.total_value)}</span>
            </div>
            <div class="compare-row">
                <span>Difference</span>
                <span class="compare-diff ${diffClass(diff.total_value_diff)}">${diffSign(diff.total_value_diff)}${formatMoney(diff.total_value_diff)}</span>
            </div>
        </div>

        <div class="compare-card">
            <h3>YTD Income</h3>
            <div class="compare-row">
                <span>${h1.name}</span>
                <span>${formatMoney(h1.ytd_income)}</span>
            </div>
            <div class="compare-row">
                <span>${h2.name}</span>
                <span>${formatMoney(h2.ytd_income)}</span>
            </div>
            <div class="compare-row">
                <span>Difference</span>
                <span class="compare-diff ${diffClass(diff.income_diff)}">${diffSign(diff.income_diff)}${formatMoney(diff.income_diff)}</span>
            </div>
        </div>

        <div class="compare-card">
            <h3>Holdings Differences</h3>
            ${Object.entries(diff.holdings_diff).map(([ticker, d]) => `
                <div class="compare-row">
                    <span>${ticker}</span>
                    <span class="compare-diff ${diffClass(d.value_diff)}">${diffSign(d.value_diff)}${formatMoney(d.value_diff)} (${d.diff > 0 ? '+' : ''}${d.diff.toFixed(1)} shares)</span>
                </div>
            `).join('')}
        </div>
    `;
}

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

    // Remove cluster UI
    const clusterUI = document.getElementById('cluster-ui');
    if (clusterUI) clusterUI.remove();

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
    if (realityProjection) {
        clusterSystems.push({
            id: 'reality',
            name: 'Reality',
            projection: realityProjection,
            frames: realityProjection.frames || [],
            group: null,
            isReality: true
        });
        clusterMaxMonths = realityProjection.frames?.length || 36;
    }

    // Load alternate history projections
    const altResponse = await fetch('/api/alt-history');
    const altData = await altResponse.json();

    for (const history of (altData.histories || [])) {
        const projection = await generateOrLoadProjection(history.id);
        if (projection) {
            clusterSystems.push({
                id: history.id,
                name: history.name,
                projection: projection,
                frames: projection.frames || [],
                group: null,
                isReality: false
            });
        }
    }
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

    clusterSystems.forEach(sys => {
        if (!sys.frames || sys.frames.length === 0 || !sys.group) return;

        // Get frame at current position
        const frameIndex = Math.floor(position * (sys.frames.length - 1));
        const frame = sys.frames[frameIndex];

        if (!frame) return;

        // Update sun size based on total value
        const initialValue = sys.frames[0]?.total_value || 1;
        const currentValue = frame.total_value || initialValue;
        const growthFactor = currentValue / initialValue;
        const sunScale = 1 + (growthFactor - 1) * 0.5; // Subtle scaling

        if (sys.group.userData.sun) {
            sys.group.userData.sun.scale.setScalar(Math.max(0.5, Math.min(3, sunScale)));
        }

        // Update planets based on holdings in frame
        const planets = sys.group.userData.planets || [];
        const holdings = frame.holdings || [];

        planets.forEach((planet, i) => {
            if (holdings[i]) {
                const holding = holdings[i];
                const initialHolding = sys.frames[0]?.holdings?.[i];
                if (initialHolding) {
                    const holdingGrowth = holding.value / (initialHolding.value || 1);
                    const planetScale = 0.5 + holdingGrowth * 0.5;
                    planet.scale.setScalar(Math.max(0.3, Math.min(2, planetScale)));
                }
            }
        });

        // Store current value for leaderboard
        sys.currentValue = currentValue;
        sys.growthPercent = ((currentValue / initialValue) - 1) * 100;
    });

    // Update date display
    if (clusterSystems[0]?.frames) {
        const frameIndex = Math.floor(position * (clusterSystems[0].frames.length - 1));
        const frame = clusterSystems[0].frames[frameIndex];
        if (frame?.date) {
            document.getElementById('cluster-date').textContent = frame.date;
        }
    }

    // Update slider
    document.getElementById('cluster-timeline-slider').value = position * 100;

    // Update leaderboard
    updateClusterLeaderboard();
}

function updateClusterLeaderboard() {
    const container = document.getElementById('leaderboard-items');
    if (!container) return;

    // Sort systems by current value
    const sorted = [...clusterSystems]
        .filter(s => s.currentValue !== undefined)
        .sort((a, b) => b.currentValue - a.currentValue);

    if (sorted.length === 0) {
        container.innerHTML = '<p style="color: #666; font-size: 12px;">Move timeline to see rankings</p>';
        return;
    }

    container.innerHTML = sorted.map((sys, index) => {
        const rankClass = index === 0 ? 'gold' : index === 1 ? 'silver' : index === 2 ? 'bronze' : 'other';
        const nameClass = sys.isReality ? 'reality' : '';
        const valueClass = sys.growthPercent >= 0 ? '' : 'negative';
        const growthSign = sys.growthPercent >= 0 ? '+' : '';

        return `
            <div class="leaderboard-item">
                <span class="leaderboard-rank ${rankClass}">${index + 1}</span>
                <span class="leaderboard-name ${nameClass}">${sys.name}</span>
                <span class="leaderboard-value ${valueClass}">${growthSign}${sys.growthPercent?.toFixed(1) || 0}%</span>
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

function togglePlaybackExpand() {
    const panel = document.getElementById('playback-panel');
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

        // Create the mysterious Alternate Reality pyramid
        createAlternateRealityPyramid();

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
