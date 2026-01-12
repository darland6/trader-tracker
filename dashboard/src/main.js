/**
 * Financial Portfolio 3D Visualization - Main Entry Point
 * Modular ES6 refactored version
 */

import * as THREE from 'three';
import gsap from 'gsap';

// Import modules
import { initScene, scene, camera, renderer, controls, updateControls, renderScene, DEFAULT_CAMERA_POS, DEFAULT_TARGET, raycaster, mouse } from './scene.js';
import {  fetchPortfolioData, updatePrices, fetchEvents, fetchLLMConfig, fetchDexterStatus,
         checkSetupStatus, checkDemoMode, initDemo, initFresh, uploadCSV, exitDemo } from './api.js';
import { createSun, createPlanet, updatePlanets, planets, sun, clearPlanets } from './planets.js';

// Global state
let portfolioData = null;
let clock = new THREE.Clock();
let isDemoMode = false;
let selectedPlanet = null;
let hoveredObject = null;

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

/**
 * Initialize Three.js scene
 */
function init() {
    initScene();
    createSun();

    // Handle click interactions
    renderer.domElement.addEventListener('click', onCanvasClick);
    renderer.domElement.addEventListener('mousemove', onCanvasMouseMove);

    // Start animation
    animate();
}

/**
 * Main animation loop
 */
function animate() {
    requestAnimationFrame(animate);

    const deltaTime = clock.getDelta();

    // Update camera animation
    updateCameraAnimation(deltaTime);

    // Update controls
    updateControls();

    // Update planets
    updatePlanets(deltaTime);

    // Render scene
    renderScene();
}

/**
 * Update camera animation
 */
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
        controls.autoRotate = selectedPlanet === null;
    }
}

/**
 * Animate camera to position
 */
function animateCameraTo(targetPos, lookAtPos, duration = 1.5) {
    controls.autoRotate = false;

    cameraAnimation.startPos.copy(camera.position);
    cameraAnimation.endPos.copy(targetPos);
    cameraAnimation.startTarget.copy(controls.target);
    cameraAnimation.endTarget.copy(lookAtPos);
    cameraAnimation.duration = duration;
    cameraAnimation.elapsed = 0;
    cameraAnimation.active = true;
}

/**
 * Focus on planet
 */
function focusOnPlanet(ticker) {
    const planetData = planets.get(ticker);
    if (!planetData) return;

    const planetGroup = planetData.group;
    const planetPos = planetGroup.position.clone();

    // Calculate camera position (behind and above the planet)
    const offset = new THREE.Vector3(0, 8, 15);
    offset.applyQuaternion(camera.quaternion);
    const targetCameraPos = planetPos.clone().add(offset);

    animateCameraTo(targetCameraPos, planetPos);

    selectedPlanet = ticker;
}

/**
 * Zoom to system view
 */
function zoomToSystem() {
    animateCameraTo(DEFAULT_CAMERA_POS, DEFAULT_TARGET);
    selectedPlanet = null;
}

/**
 * Handle canvas click
 */
function onCanvasClick(event) {
    // Calculate mouse position in normalized device coordinates
    mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
    mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

    // Update the picking ray with the camera and mouse position
    raycaster.setFromCamera(mouse, camera);

    // Check for intersections with planets
    const intersectableObjects = [];
    planets.forEach((data, ticker) => {
        if (data.group) {
            const planet = data.group.userData.planet;
            if (planet) intersectableObjects.push(planet);
        }
    });

    const intersects = raycaster.intersectObjects(intersectableObjects, true);

    if (intersects.length > 0) {
        // Find which planet was clicked
        const clickedObject = intersects[0].object;
        planets.forEach((data, ticker) => {
            if (data.group && data.group.userData.planet === clickedObject) {
                if (selectedPlanet === ticker) {
                    // Double click - zoom out
                    zoomToSystem();
                } else {
                    // Focus on this planet
                    focusOnPlanet(ticker);
                }
            }
        });
    } else if (sun && raycaster.intersectObject(sun, true).length > 0) {
        // Clicked on sun - zoom to system view
        zoomToSystem();
    }
}

/**
 * Handle canvas mouse move
 */
function onCanvasMouseMove(event) {
    mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
    mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);

    const intersectableObjects = [];
    planets.forEach((data, ticker) => {
        if (data.group) {
            const planet = data.group.userData.planet;
            if (planet) intersectableObjects.push(planet);
        }
    });
    if (sun) intersectableObjects.push(sun);

    const intersects = raycaster.intersectObjects(intersectableObjects, true);

    if (intersects.length > 0) {
        document.body.style.cursor = 'pointer';
        hoveredObject = intersects[0].object;
    } else {
        document.body.style.cursor = 'default';
        hoveredObject = null;
    }
}

/**
 * Update HUD with portfolio data
 */
function updateHUD(data) {
    document.getElementById('total-value').textContent =
        '$' + data.total_value.toLocaleString('en-US', { maximumFractionDigits: 0 });

    const cashEl = document.getElementById('cash-value');
    const availableCash = data.cash_breakdown?.available || data.cash;
    const taxReserve = data.cash_breakdown?.tax_reserve || 0;
    cashEl.textContent = '$' + availableCash.toLocaleString('en-US', { maximumFractionDigits: 0 });
    cashEl.title = `Total: $${data.cash.toLocaleString()} | Tax Reserve: $${taxReserve.toLocaleString()}`;

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

    // Add Cash card first
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
        const dayIsUp = (h.day_change_pct || 0) >= 0;
        const hasDayChange = Math.abs(h.day_change_pct || 0) >= 0.01;
        const card = document.createElement('div');
        card.className = 'holding-card' + (isGain ? '' : ' loss');
        card.innerHTML = `
            <div class="holding-ticker">${h.ticker}</div>
            <div class="holding-value">$${h.market_value.toLocaleString('en-US', { maximumFractionDigits: 0 })}</div>
            <div class="holding-gain ${isGain ? 'positive' : 'negative'}">
                ${isGain ? '+' : ''}${h.unrealized_gain_pct.toFixed(1)}%
            </div>
            ${hasDayChange ? `
            <div class="holding-day-change ${dayIsUp ? 'positive' : 'negative'}" style="font-size: 9px; margin-top: 2px;">
                ${dayIsUp ? '▲' : '▼'} ${dayIsUp ? '+' : ''}${(h.day_change_pct || 0).toFixed(2)}% today
            </div>
            ` : `<div class="holding-shares">${h.shares.toLocaleString()} shares</div>`}
        `;

        card.onclick = () => focusOnPlanet(h.ticker);
        grid.appendChild(card);
    });
}

/**
 * Check AI/MCP status
 */
async function checkAIStatus() {
    try {
        const llmData = await fetchLLMConfig();
        if (llmData) {
            updateStatusIndicator('llm-status', llmData.enabled,
                llmData.provider + ': ' + (llmData.local_model || llmData.claude_model));
        }
    } catch (e) {
        updateStatusIndicator('llm-status', false, 'LLM unavailable');
    }

    try {
        const dexterData = await fetchDexterStatus();
        if (dexterData) {
            const mcpAvailable = dexterData.status?.mcp_available || false;
            const mcpName = dexterData.status?.mcp?.name || 'dexter-mcp';
            updateStatusIndicator('mcp-status', mcpAvailable,
                mcpAvailable ? `${mcpName} connected` : 'MCP offline');
        }
    } catch (e) {
        updateStatusIndicator('mcp-status', false, 'Dexter unavailable');
    }
}

/**
 * Update status indicator
 */
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

/**
 * Refresh prices
 */
async function refreshPrices() {
    const button = document.getElementById('btn-refresh');
    const originalText = button?.textContent;
    if (button) button.textContent = '⟳';

    const success = await updatePrices();

    if (success) {
        // Reload portfolio data
        portfolioData = await fetchPortfolioData();
        if (portfolioData) {
            // Rebuild visualization
            clearPlanets();
            const totalValue = portfolioData.total_value || portfolioData.portfolio_value;
            portfolioData.holdings.forEach((holding, index) => {
                createPlanet(holding, index, portfolioData.holdings.length, totalValue);
            });
            updateHUD(portfolioData);
        }
    }

    if (button) {
        setTimeout(() => {
            button.textContent = originalText;
        }, 1000);
    }
}

/**
 * Navigate to page
 */
function navigateTo(path) {
    window.location.href = path;
}

/**
 * Show demo banner
 */
function showDemoBanner() {
    isDemoMode = true;
    const banner = document.createElement('div');
    banner.id = 'demo-banner';
    banner.innerHTML = `
        <span>Demo Mode</span>
        <button onclick="exitDemoMode()">Exit Demo</button>
    `;
    banner.style.cssText = `
        position: fixed; top: 0; left: 0; right: 0; background: linear-gradient(90deg, #ff6b00, #ff9500);
        color: white; padding: 8px 16px; text-align: center; z-index: 10000; font-weight: 600;
        display: flex; justify-content: center; align-items: center; gap: 16px;
    `;
    document.body.appendChild(banner);
}

/**
 * Exit demo mode
 */
async function exitDemoMode() {
    if (confirm('Exit demo mode? This will clear demo data.')) {
        await exitDemo();
        location.reload();
    }
}

// Make functions globally available
window.focusOnPlanet = focusOnPlanet;
window.zoomToSystem = zoomToSystem;
window.navigateTo = navigateTo;
window.refreshPrices = refreshPrices;
window.exitDemoMode = exitDemoMode;

/**
 * Main initialization
 */
async function main() {
    // Check setup status first
    const status = await checkSetupStatus();

    if (status && (status.needs_setup || status.mode === 'none')) {
        // No data exists - show setup screen (would need setup UI module)
        console.log('Setup required');
        document.getElementById('loading').innerHTML = `
            <p style="color: #ffaa00;">Setup required</p>
            <p>Please initialize the system through the web UI at <a href="http://localhost:8000">localhost:8000</a></p>
        `;
        return;
    }

    // Check if we're in demo mode
    const demoStatus = await checkDemoMode();
    if (demoStatus && demoStatus.is_demo) {
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

        // Use total portfolio value for relative sizing
        const totalValue = portfolioData.total_value || portfolioData.portfolio_value;

        // Create planets for each holding
        portfolioData.holdings.forEach((holding, index) => {
            createPlanet(holding, index, portfolioData.holdings.length, totalValue);
        });

        // Check AI/MCP status
        checkAIStatus();
        setInterval(checkAIStatus, 30000);
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
