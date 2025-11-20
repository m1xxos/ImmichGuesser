// API Configuration
const API_BASE_URL = '/api';

// Global state
let token = localStorage.getItem('token');
let currentUser = null;
let currentGame = null;
let map = null;
let resultMap = null;
let guessMarker = null;
let currentGuess = null;

// Utility: API fetch with auth
async function apiFetch(endpoint, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };
    
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...options,
        headers
    });
    
    if (response.status === 401) {
        // Token expired or invalid
        logout();
        throw new Error('Unauthorized');
    }
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'An error occurred');
    }
    
    // Handle 204 No Content responses
    if (response.status === 204) {
        return null;
    }
    
    return response.json();
}

// Screen management
function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(screen => {
        screen.classList.add('hidden');
    });
    document.getElementById(screenId).classList.remove('hidden');
}

// Authentication
async function login(username, password) {
    try {
        const data = await apiFetch('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ username, password })
        });
        
        token = data.access_token;
        localStorage.setItem('token', token);
        
        await loadCurrentUser();
        showScreen('menu-screen');
        checkActiveGame();
    } catch (error) {
        document.getElementById('login-error').textContent = error.message;
    }
}

async function register(username, email, password) {
    try {
        await apiFetch('/auth/register', {
            method: 'POST',
            body: JSON.stringify({ username, email, password })
        });
        
        // Auto-login after registration
        await login(username, password);
    } catch (error) {
        document.getElementById('register-error').textContent = error.message;
    }
}

function logout() {
    token = null;
    currentUser = null;
    currentGame = null;
    localStorage.removeItem('token');
    showScreen('auth-screen');
}

async function loadCurrentUser() {
    try {
        currentUser = await apiFetch('/auth/me');
        document.getElementById('username-display').textContent = currentUser.username;
    } catch (error) {
        logout();
    }
}

// Game functions
async function checkActiveGame() {
    try {
        currentGame = await apiFetch('/game/current');
        document.getElementById('continue-game-btn').classList.remove('hidden');
    } catch (error) {
        document.getElementById('continue-game-btn').classList.add('hidden');
    }
}

async function startNewGame() {
    try {
        // Delete current game if exists
        try {
            await apiFetch('/game/current', { method: 'DELETE' });
        } catch (e) {
            // Ignore if no game exists
        }
        
        currentGame = await apiFetch('/game/start', {
            method: 'POST',
            body: JSON.stringify({})
        });
        
        showScreen('game-screen');
        initializeMap();
        loadCurrentRound();
    } catch (error) {
        alert(`Error starting game: ${error.message}`);
    }
}

async function continueGame() {
    showScreen('game-screen');
    initializeMap();
    await loadCurrentRound();
}

async function loadCurrentRound() {
    try {
        // Get current game state
        currentGame = await apiFetch('/game/current');
        
        // Update UI
        document.getElementById('current-round').textContent = currentGame.rounds_completed + 1;
        document.getElementById('total-score').textContent = currentGame.total_score;
        
        // Load photo
        const photo = await apiFetch('/game/photo');
        const photoImg = document.getElementById('game-photo');
        const photoLoading = document.getElementById('photo-loading');
        
        photoLoading.style.display = 'block';
        photoImg.style.display = 'none';
        
        console.log('Loading photo URL:', photo.photo_url);
        
        // Load image with authentication
        try {
            const photoUrl = photo.photo_url.startsWith('http') ? photo.photo_url : API_BASE_URL + photo.photo_url;
            const response = await fetch(photoUrl, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const blob = await response.blob();
            const objectUrl = URL.createObjectURL(blob);
            
            photoImg.onload = () => {
                console.log('Photo loaded successfully');
                photoLoading.style.display = 'none';
                photoImg.style.display = 'block';
                // Clean up old object URL if exists
                if (photoImg.dataset.objectUrl) {
                    URL.revokeObjectURL(photoImg.dataset.objectUrl);
                }
                photoImg.dataset.objectUrl = objectUrl;
            };
            
            photoImg.onerror = (error) => {
                console.error('Photo loading failed:', error);
                photoLoading.style.display = 'none';
                photoImg.style.display = 'block';
                photoImg.alt = 'Failed to load image';
                URL.revokeObjectURL(objectUrl);
            };
            
            photoImg.src = objectUrl;
        } catch (error) {
            console.error('Error fetching photo:', error);
            photoLoading.style.display = 'none';
            photoImg.alt = 'Failed to load image';
        }
        
        // Reset guess
        currentGuess = null;
        if (guessMarker) {
            map.removeLayer(guessMarker);
            guessMarker = null;
        }
        document.getElementById('submit-guess-btn').disabled = true;
        document.getElementById('next-round-btn').classList.add('hidden');
        document.getElementById('finish-game-btn').classList.add('hidden');
        
    } catch (error) {
        if (error.message.includes('All rounds completed')) {
            showGameComplete();
        } else {
            alert(`Error loading round: ${error.message}`);
        }
    }
}

async function submitGuess() {
    if (!currentGuess) return;
    
    try {
        const result = await apiFetch('/game/guess', {
            method: 'POST',
            body: JSON.stringify({
                latitude: currentGuess.lat,
                longitude: currentGuess.lng
            })
        });
        
        // Show result modal
        showResult(result);
        
        // Update score
        document.getElementById('total-score').textContent = 
            parseInt(document.getElementById('total-score').textContent) + result.score;
        
        // Show appropriate button
        if (result.game_completed) {
            document.getElementById('finish-game-btn').classList.remove('hidden');
        }
        
        document.getElementById('submit-guess-btn').disabled = true;
        
    } catch (error) {
        alert(`Error submitting guess: ${error.message}`);
    }
}

function showResult(result) {
    // Show modal
    document.getElementById('result-modal').classList.remove('hidden');
    
    // Update result info
    document.getElementById('result-distance').textContent = result.distance_km.toFixed(2);
    document.getElementById('result-score').textContent = result.score;
    
    // Add link to original photo if available
    const immichLink = document.getElementById('result-immich-link');
    if (result.immich_url) {
        immichLink.href = result.immich_url;
        immichLink.style.display = 'inline-block';
    } else {
        immichLink.style.display = 'none';
    }
    
    // Initialize result map if not exists
    if (!resultMap) {
        resultMap = L.map('result-map').setView([0, 0], 2);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(resultMap);
    }
    
    // Clear previous markers
    resultMap.eachLayer(layer => {
        if (layer instanceof L.Marker) {
            resultMap.removeLayer(layer);
        }
    });
    
    // Add markers for guess and actual location
    const guessMarkerIcon = L.icon({
        iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
        iconSize: [25, 41],
        iconAnchor: [12, 41],
        popupAnchor: [1, -34],
        shadowSize: [41, 41]
    });
    
    const actualMarkerIcon = L.icon({
        iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
        iconSize: [25, 41],
        iconAnchor: [12, 41],
        popupAnchor: [1, -34],
        shadowSize: [41, 41]
    });
    
    const guessMarkerResult = L.marker([currentGuess.lat, currentGuess.lng], {icon: guessMarkerIcon})
        .addTo(resultMap)
        .bindPopup('Your Guess');
    
    const actualMarkerResult = L.marker([result.actual_latitude, result.actual_longitude], {icon: actualMarkerIcon})
        .addTo(resultMap)
        .bindPopup('Actual Location');
    
    // Draw line between them
    const line = L.polyline([
        [currentGuess.lat, currentGuess.lng],
        [result.actual_latitude, result.actual_longitude]
    ], {color: 'blue', weight: 2, opacity: 0.7}).addTo(resultMap);
    
    // Fit bounds to show both markers
    const bounds = L.latLngBounds([
        [currentGuess.lat, currentGuess.lng],
        [result.actual_latitude, result.actual_longitude]
    ]);
    resultMap.fitBounds(bounds, {padding: [50, 50]});
    
    // Force map to redraw
    setTimeout(() => resultMap.invalidateSize(), 100);
}

function closeResult() {
    document.getElementById('result-modal').classList.add('hidden');
    // Load next round after closing result
    loadCurrentRound();
}

async function nextRound() {
    closeResult();
}

async function showGameComplete() {
    try {
        currentGame = await apiFetch('/game/current');
        const rounds = await apiFetch('/game/rounds');
        
        showScreen('complete-screen');
        
        document.getElementById('final-score-display').textContent = currentGame.total_score;
        
        // Show rounds summary
        const summaryContainer = document.getElementById('rounds-summary');
        summaryContainer.innerHTML = '<h3>Round Summary</h3>';
        
        rounds.forEach(round => {
            if (round.score !== undefined) {
                const roundDiv = document.createElement('div');
                roundDiv.className = 'round-summary-item';
                roundDiv.innerHTML = `
                    <strong>Round ${round.round_number}:</strong> 
                    ${round.distance_km?.toFixed(2) || 'N/A'} km - 
                    ${round.score} points
                `;
                summaryContainer.appendChild(roundDiv);
            }
        });
        
    } catch (error) {
        console.error('Error showing game complete:', error);
    }
}

async function quitGame() {
    if (confirm('Are you sure you want to quit? Your progress will be lost.')) {
        try {
            await apiFetch('/game/current', { method: 'DELETE' });
            currentGame = null;
            currentGuess = null;
            if (guessMarker) {
                map.removeLayer(guessMarker);
                guessMarker = null;
            }
            showScreen('menu-screen');
            await checkActiveGame();
        } catch (error) {
            alert(`Error quitting game: ${error.message}`);
        }
    }
}

async function loadLeaderboard() {
    try {
        const data = await apiFetch('/game/leaderboard?limit=10');
        
        const tbody = document.getElementById('leaderboard-body');
        tbody.innerHTML = '';
        
        if (data.entries.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4">No games completed yet</td></tr>';
            return;
        }
        
        data.entries.forEach((entry, index) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${index + 1}</td>
                <td>${entry.username}</td>
                <td>${entry.total_score}</td>
                <td>${new Date(entry.completed_at).toLocaleDateString()}</td>
            `;
            tbody.appendChild(row);
        });
        
        showScreen('leaderboard-screen');
    } catch (error) {
        alert(`Error loading leaderboard: ${error.message}`);
    }
}

// Map initialization
function initializeMap() {
    if (map) {
        map.remove();
    }
    
    map = L.map('map').setView([20, 0], 2);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(map);
    
    // Click handler for guesses
    map.on('click', (e) => {
        currentGuess = e.latlng;
        
        // Remove previous marker
        if (guessMarker) {
            map.removeLayer(guessMarker);
        }
        
        // Add new marker
        guessMarker = L.marker([e.latlng.lat, e.latlng.lng]).addTo(map);
        
        // Enable submit button
        document.getElementById('submit-guess-btn').disabled = false;
    });
}

// Event listeners
document.addEventListener('DOMContentLoaded', () => {
    // Auth tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.auth-form').forEach(f => f.classList.remove('active'));
            
            btn.classList.add('active');
            document.getElementById(`${tab}-form`).classList.add('active');
        });
    });
    
    // Login form
    document.getElementById('login').addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('login-username').value;
        const password = document.getElementById('login-password').value;
        await login(username, password);
    });
    
    // Register form
    document.getElementById('register').addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('register-username').value;
        const email = document.getElementById('register-email').value;
        const password = document.getElementById('register-password').value;
        await register(username, email, password);
    });
    
    // Menu buttons
    document.getElementById('start-game-btn').addEventListener('click', startNewGame);
    document.getElementById('continue-game-btn').addEventListener('click', continueGame);
    document.getElementById('leaderboard-btn').addEventListener('click', loadLeaderboard);
    document.getElementById('logout-btn').addEventListener('click', logout);
    
    // Game buttons
    document.getElementById('submit-guess-btn').addEventListener('click', submitGuess);
    document.getElementById('next-round-btn').addEventListener('click', nextRound);
    document.getElementById('finish-game-btn').addEventListener('click', showGameComplete);
    document.getElementById('quit-game-btn').addEventListener('click', quitGame);
    document.getElementById('close-result-btn').addEventListener('click', closeResult);
    
    // Complete screen buttons
    document.getElementById('play-again-btn').addEventListener('click', startNewGame);
    document.getElementById('view-leaderboard-btn').addEventListener('click', loadLeaderboard);
    document.getElementById('back-to-menu-btn').addEventListener('click', () => {
        showScreen('menu-screen');
        checkActiveGame();
    });
    document.getElementById('back-to-menu-btn-2').addEventListener('click', () => {
        showScreen('menu-screen');
        checkActiveGame();
    });
    
    // Leaderboard back button
    document.getElementById('back-to-menu-btn').addEventListener('click', () => {
        showScreen('menu-screen');
    });
    
    // Initialize
    if (token) {
        loadCurrentUser().then(() => {
            showScreen('menu-screen');
            checkActiveGame();
        }).catch(() => {
            showScreen('auth-screen');
        });
    } else {
        showScreen('auth-screen');
    }
});
