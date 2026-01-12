import * as THREE from 'three';
import { scene } from './scene.js';

// Global state
export let planets = new Map();
export let sun;

/**
 * Create the central sun (portfolio total)
 */
export function createSun() {
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

    return sun;
}

/**
 * Generate realistic planet texture
 */
export function createPlanetTexture(baseColor, isGain) {
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

/**
 * Create atmosphere/glow for planet
 */
export function createAtmosphere(radius, isGain, intensity) {
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

/**
 * Create momentum particles around planet
 */
export function createMomentumParticles(radius, momentum) {
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

/**
 * Create intraday change indicator (pulsing arrow beam)
 */
export function createDayChangeIndicator(radius, dayChangePct) {
    const group = new THREE.Group();

    // Only show if there's a meaningful day change (>0.1%)
    if (Math.abs(dayChangePct) < 0.1) return group;

    const isPositive = dayChangePct >= 0;
    const color = isPositive ? 0x00ff88 : 0xff4444;
    const intensity = Math.min(Math.abs(dayChangePct) / 5, 1); // Cap at 5% for max intensity

    // Arrow direction (up for gain, down for loss)
    const direction = isPositive ? 1 : -1;

    // Create vertical beam/spire
    const beamHeight = radius * (0.8 + intensity * 1.2);
    const beamGeometry = new THREE.CylinderGeometry(0.05, 0.15, beamHeight, 8);
    const beamMaterial = new THREE.MeshBasicMaterial({
        color: color,
        transparent: true,
        opacity: 0.6 + intensity * 0.3,
        blending: THREE.AdditiveBlending
    });
    const beam = new THREE.Mesh(beamGeometry, beamMaterial);
    beam.position.y = direction * (radius + beamHeight / 2 + 0.2);
    beam.rotation.z = isPositive ? 0 : Math.PI; // Flip for down arrow
    group.add(beam);

    // Arrow head (cone)
    const arrowSize = 0.3 + intensity * 0.2;
    const arrowGeometry = new THREE.ConeGeometry(arrowSize, arrowSize * 1.5, 8);
    const arrowMaterial = new THREE.MeshBasicMaterial({
        color: color,
        transparent: true,
        opacity: 0.8,
        blending: THREE.AdditiveBlending
    });
    const arrow = new THREE.Mesh(arrowGeometry, arrowMaterial);
    arrow.position.y = direction * (radius + beamHeight + arrowSize * 0.75 + 0.2);
    arrow.rotation.z = isPositive ? 0 : Math.PI; // Point up or down
    group.add(arrow);

    // Pulsing glow ring at base
    const ringGeometry = new THREE.RingGeometry(radius + 0.1, radius + 0.3, 32);
    const ringMaterial = new THREE.MeshBasicMaterial({
        color: color,
        transparent: true,
        opacity: 0.4 + intensity * 0.4,
        side: THREE.DoubleSide,
        blending: THREE.AdditiveBlending
    });
    const ring = new THREE.Mesh(ringGeometry, ringMaterial);
    ring.rotation.x = Math.PI / 2;
    ring.position.y = direction * radius * 0.3;
    group.add(ring);

    // Store animation data
    group.userData = {
        type: 'dayChangeIndicator',
        dayChangePct,
        isPositive,
        intensity,
        beam,
        arrow,
        ring,
        pulsePhase: Math.random() * Math.PI * 2
    };

    return group;
}

/**
 * Helper to create partial ring (arc)
 */
export function createPartialRing(innerRadius, outerRadius, startAngle, endAngle, color) {
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

/**
 * Create main planet for a holding
 */
export function createPlanet(holding, index, total, portfolioTotal) {
    const { ticker, shares, market_value, unrealized_gain_pct, current_price, day_change_pct = 0 } = holding;

    // Calculate size based on position size (relative to total portfolio value)
    const sizeRatio = market_value / portfolioTotal;
    const allocationPct = sizeRatio * 100;
    const radius = 0.8 + sizeRatio * 8;

    // Momentum simulation
    const momentum = unrealized_gain_pct / 100;
    const isGain = unrealized_gain_pct >= 0;

    // ORBIT DISTANCE: Based on allocation
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

    // Create planet mesh
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

    // Create planet group
    const planetGroup = new THREE.Group();
    planetGroup.add(planet);

    // Add atmosphere glow
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

    // Add intraday change indicator
    const dayChangeIndicator = createDayChangeIndicator(radius, day_change_pct);
    if (dayChangeIndicator.children.length > 0) {
        planetGroup.add(dayChangeIndicator);
    }

    // Position in orbit
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
        day_change_pct,
        allocation_pct: allocationPct,
        orbitRadius,
        orbitSpeed: 0.0003 + (1 - sizeRatio) * 0.0005,
        orbitAngle: angle,
        rotationSpeed: 0.002 + Math.random() * 0.002,
        momentum,
        particles,
        planet,
        dayChangeIndicator
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

/**
 * Update planets animation
 */
export function updatePlanets(deltaTime) {
    planets.forEach((data, ticker) => {
        if (!data.group || !data.group.userData) return;
        const userData = data.group.userData;

        // Skip non-standard planets
        if (userData.type !== 'planet' && userData.type !== 'cash-planet') return;

        // Orbit around sun
        if (userData.orbitSpeed) {
            userData.orbitAngle += userData.orbitSpeed;
            data.group.position.x = Math.cos(userData.orbitAngle) * userData.orbitRadius;
            data.group.position.z = Math.sin(userData.orbitAngle) * userData.orbitRadius;
        }

        // Rotate planet
        if (userData.planet && userData.rotationSpeed) {
            userData.planet.rotation.y += userData.rotationSpeed;
        }

        // Rotate particles
        if (userData.particles) {
            userData.particles.rotation.y += 0.005;
        }

        // Animate day change indicator (pulsing)
        if (userData.dayChangeIndicator) {
            const indicator = userData.dayChangeIndicator;
            if (indicator.userData && indicator.userData.type === 'dayChangeIndicator') {
                indicator.userData.pulsePhase += deltaTime * 2;
                const pulse = 0.8 + Math.sin(indicator.userData.pulsePhase) * 0.2;

                if (indicator.userData.beam) {
                    indicator.userData.beam.material.opacity = (0.6 + indicator.userData.intensity * 0.3) * pulse;
                }
                if (indicator.userData.arrow) {
                    indicator.userData.arrow.material.opacity = 0.8 * pulse;
                }
                if (indicator.userData.ring) {
                    indicator.userData.ring.scale.setScalar(1 + Math.sin(indicator.userData.pulsePhase * 0.5) * 0.1);
                }
            }
        }

        // Animate moons for cash planet
        if (userData.type === 'cash-planet') {
            data.group.children.forEach(child => {
                if (child.userData && child.userData.type === 'cash-moon') {
                    child.userData.orbitAngle += child.userData.orbitSpeed;
                    child.position.x = Math.cos(child.userData.orbitAngle) * child.userData.orbitRadius;
                    child.position.z = Math.sin(child.userData.orbitAngle) * child.userData.orbitRadius;
                }
            });
        }
    });
}

/**
 * Clear all planets from scene
 */
export function clearPlanets() {
    planets.forEach((data, ticker) => {
        if (data.group) scene.remove(data.group);
        if (data.orbit) scene.remove(data.orbit);
    });
    planets.clear();
}
