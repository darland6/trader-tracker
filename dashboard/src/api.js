/**
 * API Module - All backend API calls
 */

/**
 * Fetch portfolio state
 */
export async function fetchPortfolioData() {
    try {
        const response = await fetch('/api/state');
        if (!response.ok) throw new Error('Failed to fetch');
        return await response.json();
    } catch (error) {
        console.error('Error fetching portfolio:', error);
        return null;
    }
}

/**
 * Fetch price quote for a ticker
 */
export async function fetchPriceQuote(ticker) {
    try {
        const response = await fetch(`/api/prices/quote?ticker=${ticker}`);
        if (response.ok) {
            return await response.json();
        }
        return null;
    } catch (error) {
        console.error('Failed to fetch price quote:', error);
        return null;
    }
}

/**
 * Update all stock prices
 */
export async function updatePrices() {
    try {
        const response = await fetch('/api/prices/update', { method: 'POST' });
        return response.ok;
    } catch (error) {
        console.error('Failed to update prices:', error);
        return false;
    }
}

/**
 * Fetch event history
 */
export async function fetchEvents(limit = 5000) {
    try {
        const response = await fetch(`/api/events?limit=${limit}`);
        if (!response.ok) throw new Error('Failed to fetch');
        return await response.json();
    } catch (error) {
        console.error('Error fetching events:', error);
        return null;
    }
}

/**
 * Fetch event snapshot by event ID
 */
export async function fetchEventSnapshot(eventId) {
    try {
        const response = await fetch(`/api/history/snapshot/${eventId}`);
        if (!response.ok) throw new Error('Failed to fetch snapshot');
        return await response.json();
    } catch (error) {
        console.error('Error fetching snapshot:', error);
        return null;
    }
}

/**
 * Fetch prepared playback timeline
 */
export async function fetchPlaybackTimeline() {
    try {
        const response = await fetch('/api/history/prepared-playback');
        if (!response.ok) throw new Error('Failed to fetch timeline');
        return await response.json();
    } catch (error) {
        console.error('Error fetching playback timeline:', error);
        return null;
    }
}

/**
 * Fetch alternate histories
 */
export async function fetchAlternateHistories() {
    try {
        const response = await fetch('/api/alt-history');
        if (!response.ok) throw new Error('Failed to fetch');
        return await response.json();
    } catch (error) {
        console.error('Error fetching alternate histories:', error);
        return null;
    }
}

/**
 * Fetch single alternate history
 */
export async function fetchAlternateHistory(historyId) {
    try {
        const response = await fetch(`/api/alt-history/${historyId}`);
        if (!response.ok) throw new Error('Failed to fetch');
        return await response.json();
    } catch (error) {
        console.error('Error fetching alternate history:', error);
        return null;
    }
}

/**
 * Compare alternate histories
 */
export async function compareHistories(id1, id2) {
    try {
        const response = await fetch(`/api/alt-history/${id1}/compare/${id2}`);
        if (!response.ok) throw new Error('Failed to compare');
        return await response.json();
    } catch (error) {
        console.error('Error comparing histories:', error);
        return null;
    }
}

/**
 * Create alternate history
 */
export async function createAlternateHistory(data) {
    try {
        const response = await fetch('/api/alt-history', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!response.ok) throw new Error('Failed to create');
        return await response.json();
    } catch (error) {
        console.error('Error creating alternate history:', error);
        return null;
    }
}

/**
 * Delete alternate history
 */
export async function deleteAlternateHistory(historyId) {
    try {
        const response = await fetch(`/api/alt-history/${historyId}`, { method: 'DELETE' });
        return response.ok;
    } catch (error) {
        console.error('Error deleting alternate history:', error);
        return false;
    }
}

/**
 * Generate future projection
 */
export async function generateProjection(data) {
    try {
        const response = await fetch('/api/alt-history/projections/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!response.ok) throw new Error('Failed to generate projection');
        return await response.json();
    } catch (error) {
        console.error('Error generating projection:', error);
        return null;
    }
}

/**
 * Fetch saved projections
 */
export async function fetchProjections() {
    try {
        const response = await fetch('/api/alt-history/projections');
        if (!response.ok) throw new Error('Failed to fetch projections');
        return await response.json();
    } catch (error) {
        console.error('Error fetching projections:', error);
        return null;
    }
}

/**
 * Fetch single projection
 */
export async function fetchProjection(projectionId) {
    try {
        const response = await fetch(`/api/alt-history/projections/${projectionId}`);
        if (!response.ok) throw new Error('Failed to fetch projection');
        return await response.json();
    } catch (error) {
        console.error('Error fetching projection:', error);
        return null;
    }
}

/**
 * Delete projection
 */
export async function deleteProjection(projectionId) {
    try {
        const response = await fetch(`/api/alt-history/projections/${projectionId}`, { method: 'DELETE' });
        return response.ok;
    } catch (error) {
        console.error('Error deleting projection:', error);
        return false;
    }
}

/**
 * Fetch ideas as modifications
 */
export async function fetchIdeasAsMods() {
    try {
        const response = await fetch('/api/ideas/as-mods');
        if (!response.ok) throw new Error('Failed to fetch ideas');
        return await response.json();
    } catch (error) {
        console.error('Error fetching ideas:', error);
        return null;
    }
}

/**
 * Fetch all ideas
 */
export async function fetchIdeas() {
    try {
        const response = await fetch('/api/ideas/');
        if (!response.ok) throw new Error('Failed to fetch ideas');
        return await response.json();
    } catch (error) {
        console.error('Error fetching ideas:', error);
        return null;
    }
}

/**
 * Create new idea
 */
export async function createIdea(data) {
    try {
        const response = await fetch('/api/ideas/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!response.ok) throw new Error('Failed to create idea');
        return await response.json();
    } catch (error) {
        console.error('Error creating idea:', error);
        return null;
    }
}

/**
 * Manifest idea
 */
export async function manifestIdea(ideaId) {
    try {
        const response = await fetch(`/api/ideas/${ideaId}/manifest`, { method: 'POST' });
        if (!response.ok) throw new Error('Failed to manifest idea');
        return await response.json();
    } catch (error) {
        console.error('Error manifesting idea:', error);
        return null;
    }
}

/**
 * Archive idea
 */
export async function archiveIdea(ideaId) {
    try {
        const response = await fetch(`/api/ideas/${ideaId}/archive`, { method: 'POST' });
        return response.ok;
    } catch (error) {
        console.error('Error archiving idea:', error);
        return false;
    }
}

/**
 * Toggle idea active state
 */
export async function toggleIdeaActive(ideaId) {
    try {
        const response = await fetch(`/api/ideas/${ideaId}/toggle`, { method: 'POST' });
        return response.ok;
    } catch (error) {
        console.error('Error toggling idea:', error);
        return false;
    }
}

/**
 * Fetch research insights
 */
export async function fetchResearchInsights() {
    try {
        const response = await fetch('/api/research/insights');
        if (!response.ok) throw new Error('Failed to fetch insights');
        return await response.json();
    } catch (error) {
        console.error('Error fetching insights:', error);
        return null;
    }
}

/**
 * Fetch Dexter research status
 */
export async function fetchDexterStatus() {
    try {
        const response = await fetch('/api/research/status');
        if (!response.ok) throw new Error('Failed to fetch status');
        return await response.json();
    } catch (error) {
        console.error('Error fetching dexter status:', error);
        return null;
    }
}

/**
 * Send chat message
 */
export async function sendChatMessage(message, useStreaming = false) {
    try {
        const response = await fetch('/api/chat/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, stream: useStreaming })
        });
        if (!response.ok) throw new Error('Failed to send message');
        return await response.json();
    } catch (error) {
        console.error('Error sending chat message:', error);
        return null;
    }
}

/**
 * Fetch chat token usage
 */
export async function fetchChatUsage() {
    try {
        const response = await fetch('/api/chat/usage');
        if (!response.ok) throw new Error('Failed to fetch usage');
        return await response.json();
    } catch (error) {
        console.error('Error fetching chat usage:', error);
        return null;
    }
}

/**
 * Fetch chat session stats
 */
export async function fetchChatSession() {
    try {
        const response = await fetch('/api/chat/session');
        if (!response.ok) throw new Error('Failed to fetch session');
        return await response.json();
    } catch (error) {
        console.error('Error fetching chat session:', error);
        return null;
    }
}

/**
 * Fetch LLM configuration
 */
export async function fetchLLMConfig() {
    try {
        const response = await fetch('/api/config/llm');
        if (!response.ok) throw new Error('Failed to fetch config');
        return await response.json();
    } catch (error) {
        console.error('Error fetching LLM config:', error);
        return null;
    }
}

/**
 * Save LLM configuration
 */
export async function saveLLMConfig(config) {
    try {
        const response = await fetch('/api/config/llm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        if (!response.ok) throw new Error('Failed to save config');
        return await response.json();
    } catch (error) {
        console.error('Error saving LLM config:', error);
        return null;
    }
}

/**
 * Save LLM API key
 */
export async function saveLLMApiKey(provider, apiKey) {
    try {
        const response = await fetch('/api/config/llm/api-key', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider, api_key: apiKey })
        });
        return response.ok;
    } catch (error) {
        console.error('Error saving API key:', error);
        return false;
    }
}

/**
 * Check LLM status
 */
export async function checkLLMStatus() {
    try {
        const response = await fetch('/api/config/llm/status');
        if (!response.ok) throw new Error('Failed to check status');
        return await response.json();
    } catch (error) {
        console.error('Error checking LLM status:', error);
        return null;
    }
}

/**
 * Test LLM connection
 */
export async function testLLMConnection() {
    try {
        const response = await fetch('/api/config/llm/test', { method: 'POST' });
        if (!response.ok) throw new Error('Failed to test');
        return await response.json();
    } catch (error) {
        console.error('Error testing LLM connection:', error);
        return null;
    }
}

/**
 * Check setup status
 */
export async function checkSetupStatus() {
    try {
        const response = await fetch('/api/setup/status');
        if (!response.ok) throw new Error('Failed to check status');
        return await response.json();
    } catch (error) {
        console.error('Error checking setup status:', error);
        return null;
    }
}

/**
 * Check if demo mode
 */
export async function checkDemoMode() {
    try {
        const response = await fetch('/api/setup/is-demo');
        if (!response.ok) throw new Error('Failed to check demo mode');
        return await response.json();
    } catch (error) {
        console.error('Error checking demo mode:', error);
        return null;
    }
}

/**
 * Initialize demo mode
 */
export async function initDemo() {
    try {
        const response = await fetch('/api/setup/init-demo', { method: 'POST' });
        if (!response.ok) throw new Error('Failed to initialize demo');
        return await response.json();
    } catch (error) {
        console.error('Error initializing demo:', error);
        return null;
    }
}

/**
 * Initialize fresh setup
 */
export async function initFresh(data) {
    try {
        const response = await fetch('/api/setup/init-fresh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!response.ok) throw new Error('Failed to initialize');
        return await response.json();
    } catch (error) {
        console.error('Error initializing fresh:', error);
        return null;
    }
}

/**
 * Upload CSV
 */
export async function uploadCSV(formData) {
    try {
        const response = await fetch('/api/setup/upload-csv', {
            method: 'POST',
            body: formData
        });
        if (!response.ok) throw new Error('Failed to upload CSV');
        return await response.json();
    } catch (error) {
        console.error('Error uploading CSV:', error);
        return null;
    }
}

/**
 * Exit demo mode
 */
export async function exitDemo() {
    try {
        const response = await fetch('/api/setup/exit-demo', { method: 'POST' });
        if (!response.ok) throw new Error('Failed to exit demo');
        return await response.json();
    } catch (error) {
        console.error('Error exiting demo:', error);
        return null;
    }
}

/**
 * Fetch options scanner recommendations
 */
export async function fetchScannerRecommendations() {
    try {
        const response = await fetch('/api/scanner/recommendations');
        if (!response.ok) throw new Error('Failed to fetch recommendations');
        return await response.json();
    } catch (error) {
        console.error('Error fetching scanner recommendations:', error);
        return null;
    }
}

/**
 * Fetch analyzed scanner recommendations
 */
export async function fetchAnalyzedRecommendations() {
    try {
        const response = await fetch('/api/scanner/recommendations/analyze');
        if (!response.ok) throw new Error('Failed to fetch analyzed recommendations');
        return await response.json();
    } catch (error) {
        console.error('Error fetching analyzed recommendations:', error);
        return null;
    }
}

/**
 * Fetch agent scanner recommendations
 */
export async function fetchAgentRecommendations() {
    try {
        const response = await fetch('/api/scanner/recommendations/agent');
        if (!response.ok) throw new Error('Failed to fetch agent recommendations');
        return await response.json();
    } catch (error) {
        console.error('Error fetching agent recommendations:', error);
        return null;
    }
}
