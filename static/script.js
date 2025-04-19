// Redirect to include session_id in URL if missing
(function() {
    const urlParams = new URLSearchParams(window.location.search);
    if (!urlParams.get('session_id')) {
        const sid = sessionStorage.getItem('spotit_session_id');
        if (sid) {
            window.location.replace(window.location.pathname + '?session_id=' + sid);
        }
    }
})();

// Track which emoji is selected so highlight persists
let selectedPlayerEmoji = null;
let selectedCenterEmoji = null;

// Track last fetched emojis to avoid unnecessary re-renders
let lastPlayerData = null;
let lastCenterData = null;

/** Re-apply persisted highlights after re-render */
function applyHighlights() {
  if (selectedPlayerEmoji) {
    document.getElementById('player-circle-container')
      .querySelectorAll('.emoji').forEach(el => {
        if (el.textContent.trim() === selectedPlayerEmoji) {
          el.classList.add('highlighted');
        }
      });
  }
  if (selectedCenterEmoji) {
    document.getElementById('center-circle-container')
      .querySelectorAll('.emoji').forEach(el => {
        if (el.textContent.trim() === selectedCenterEmoji) {
          el.classList.add('highlighted');
        }
      });
  }
}

function arrangeEmojiForAll() {
  // Only arrange if containers exist (avoid errors on login page)
  const playerContainer = document.getElementById('player-circle-container');
  const centerContainer = document.getElementById('center-circle-container');
  if (playerContainer) arrangeEmoji('player-circle-container');
  if (centerContainer) arrangeEmoji('center-circle-container');
}

function arrangeEmoji(containerId) {
  const container = document.getElementById(containerId);
  const emojis = container.querySelectorAll('.emoji');
  const centerX = container.offsetWidth / 2;
  const centerY = container.offsetHeight / 2;
  const radius = container.offsetWidth / 2 - 60;

  emojis.forEach((emoji) => {
    const index = parseInt(emoji.getAttribute('data-index'));

    if (index === 0) {
      // center emoji
      emoji.style.left = `${centerX - emoji.offsetWidth / 2}px`;
      emoji.style.top = `${centerY - emoji.offsetHeight / 2}px`;
    } else {
      // outer 7 emojis
      let angle = (2 * Math.PI / 7) * (index - 1); // index 1-7
      let x = centerX + radius * Math.cos(angle);
      let y = centerY + radius * Math.sin(angle);

      emoji.style.left = `${x - emoji.offsetWidth / 2}px`;
      emoji.style.top = `${y - emoji.offsetHeight / 2}px`;
    }
  });
}

function updateCard(newCenterEmojis, newPlayerEmojis) {
  const centerContainer = document.getElementById('center-circle-container');
  const playerContainer = document.getElementById('player-circle-container');

  // Clear current emojis
  centerContainer.innerHTML = '';
  playerContainer.innerHTML = '';

  if (typeof newCenterEmojis === 'string' && newCenterEmojis.startsWith("DONE")) { // game over
    const winner = newCenterEmojis.split(" ")[1];
    Swal.fire({
      title: "Game Over",
      icon: "success",
      text: `Winner is ${winner} 🎉`,
      scrollbarPadding: false
    });
  } else {
    // Add new center emojis
    newCenterEmojis.forEach(e => {
      const span = document.createElement('span');
      span.className = 'emoji';
      span.setAttribute('data-index', e.index);
      span.style.fontSize = `${e.size}px`;
      span.style.transform = `rotate(${e.rotation}deg)`;
      span.onclick = () => emojiClicked(e.emoji, false);
      span.innerText = e.emoji;
      centerContainer.appendChild(span);
    });
  }

  // Add new player emojis
  newPlayerEmojis.forEach(e => {
    const span = document.createElement('span');
    span.className = 'emoji';
    span.setAttribute('data-index', e.index);
    span.style.fontSize = `${e.size}px`;
    span.style.transform = `rotate(${e.rotation}deg)`;
    span.onclick = () => emojiClicked(e.emoji, true);
    span.innerText = e.emoji;
    playerContainer.appendChild(span);
  });

  // Re-arrange after adding
  arrangeEmojiForAll();
  // Re-apply persisted highlights
  applyHighlights();
}

function clearHighlights() {
  document.querySelectorAll('.emoji.highlighted').forEach(el => el.classList.remove('highlighted'));
}

function highlightEmoji(containerId, emojiChar) {
  const container = document.getElementById(containerId);
  // Only one selected per container; deselect if same clicked
  if (containerId === 'player-circle-container') {
    if (selectedPlayerEmoji === emojiChar) {
      selectedPlayerEmoji = null;
      container.querySelectorAll('.emoji.highlighted').forEach(el => el.classList.remove('highlighted'));
      return;
    }
    // New player selection: clear both containers
    selectedPlayerEmoji = emojiChar;
    selectedCenterEmoji = null;
  } else {
    if (selectedCenterEmoji === emojiChar) {
      selectedCenterEmoji = null;
      container.querySelectorAll('.emoji.highlighted').forEach(el => el.classList.remove('highlighted'));
      return;
    }
    // New center selection
    selectedCenterEmoji = emojiChar;
    selectedPlayerEmoji = null;
  }
  // Clear all previous highlights
  clearHighlights();
  // Highlight the newly selected emoji
  container.querySelectorAll('.emoji').forEach(el => {
    if (el.textContent.trim() === emojiChar) el.classList.add('highlighted');
  });
}

function emojiClicked(emoji, isPlayer) {
  addr = isPlayer ? '/clickedPlayer' : '/clickedCenter';
  containerId = isPlayer ? 'player-circle-container' : 'center-circle-container';
  fetchWithSession(addr, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ emoji: emoji })
  })
    .then(response => response.json())
    .then(data => { // for a nice popup message
      if (data && data.message) {
        Swal.fire({
          toast: true,
          position: 'top',
          showConfirmButton: false,
          timer: 3000,
          timerProgressBar: true,
          icon: 'info',
          title: data.message
        });
      }
      if (data && data.center_emojis && data.player_emojis) {
        updateCard(data.center_emojis, data.player_emojis);
      }
      // Handle highlight toggle and clear
      if (data && data.clear_highlight) {
        // clear on new card or shuffle
        selectedPlayerEmoji = null;
        selectedCenterEmoji = null;
        clearHighlights();
      }
      if (data && data.highlight) {
        highlightEmoji(containerId, data.highlight);
      }
      if (data && data.names && data.scores) { // update scoreboard (preserve highlight)
        if (typeof updateScoreboardWithHighlight === 'function') {
          updateScoreboardWithHighlight(data.names, data.scores);
        } else {
          updateScoreboard(data.names, data.scores);
        }
      }
    });
}

function shuffle() {
  fetchWithSession('/shuffle', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  })
    .then(response => response.json())
    .then(data => { // for a nice popup message
      if (data && data.center_emojis == "DONE") {
        Swal.fire({
          title: "Cannot Shuffled",
          icon: "error",
          text: "No more cards in the center pile",
          scrollbarPadding: false
        });
      }
      else if (data && data.center_emojis && data.player_emojis) {
        Swal.fire({ title: "Shuffled", icon: "success", scrollbarPadding: false });
        if (data.clear_highlight) {
          selectedPlayerEmoji = null;
          selectedCenterEmoji = null;
          clearHighlights();
        }
        updateCard(data.center_emojis, data.player_emojis);
      }
    });
}

function updateScoreboard(names, scores) {
  const nameRow = document.getElementById('name-row');
  const scoreRow = document.getElementById('score-row');

  nameRow.innerHTML = '';  // Clear previous content
  scoreRow.innerHTML = '';

  names.forEach(name => {
    const th = document.createElement('th');
    th.textContent = name;
    th.style.padding = '0 10px';
    nameRow.appendChild(th);
  });

  scores.forEach(score => {
    const td = document.createElement('td');
    td.textContent = score;
    td.style.textAlign = 'center';
    td.style.padding = '4px 10px';
    scoreRow.appendChild(td);
  });
}

function rotate(direction) {
  fetchWithSession('/rotate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ direction: direction })
  })
    .then(response => response.json())
    .then(data => { // for a nice popup message
      if (data && data.center_emojis && data.player_emojis) {
        // clearHighlights();
        updateCard(data.center_emojis, data.player_emojis);
      }
      if (data && data.containerId && data.highlight) {
        highlightEmoji(data.containerId, data.highlight)
      }
    });
}

function promptUsername() {
  Swal.fire({
    title: 'Enter your username',
    input: 'text',
    inputPlaceholder: 'Username',
    showCancelButton: false,
    allowOutsideClick: false,
    inputValidator: (value) => {
      if (!value) {
        return 'You need to enter a username!';
      }
    }
  }).then((result) => {
    if (result.isConfirmed) {
      const username = result.value;
      
      // Store username in sessionStorage for this tab
      sessionStorage.setItem('spotit_username', username);
      
      // Send username to server
      fetchWithSession('/set_username', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username: username }),
      })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          // Store session info in sessionStorage for this tab
          if (data.session_id) {
            sessionStorage.setItem('spotit_session_id', data.session_id);
            console.log('Stored session ID:', data.session_id);
          }
          
          if (data.username) {
            sessionStorage.setItem('spotit_username', data.username);
            console.log('Stored username:', data.username);
          }
          
          if (data.redirect) {
            // Game is ready to start, redirect to game
            window.location.href = data.redirect;
          } else {
            // Show waiting message
            const waitingCount = data.waiting_count;
            Swal.fire({
              title: 'Waiting for players',
              text: `Waiting for ${waitingCount} more players to join...`,
              icon: 'info',
              showConfirmButton: false,
              allowOutsideClick: false
            });
            
            // Update waiting count on page
            document.getElementById('waiting-count').textContent = waitingCount;
            
            // Start polling for game status
            pollGameStatus();
          }
        } else {
          // Show error message
          Swal.fire({
            title: 'Error',
            text: data.error,
            icon: 'error',
            confirmButtonText: 'Try Again'
          }).then(() => {
            promptUsername();
          });
        }
      })
      .catch(error => {
        console.error('Error:', error);
        Swal.fire({
          title: 'Error',
          text: 'There was an error joining the game. Please try again.',
          icon: 'error',
          confirmButtonText: 'Try Again'
        }).then(() => {
          promptUsername();
        });
      });
    }
  });
}

function pollGameStatus() {
  // Poll the server every 2 seconds to check if all players have joined
  const interval = setInterval(() => {
    fetchWithSession('/check_game_status')
      .then(response => response.json())
      .then(data => {
        if (data.game_ready) {
          clearInterval(interval);
          
          // Show a message before redirecting
          Swal.fire({
            title: 'Game Starting!',
            text: 'All players have joined. Starting the game...',
            icon: 'success',
            timer: 1500,
            showConfirmButton: false
          }).then(() => {
            window.location.href = data.redirect;
          });
        } else {
          // Update waiting count
          if (data.waiting_count !== undefined) {
            document.getElementById('waiting-count').textContent = data.waiting_count;
            
            // Update the Swal popup if it exists
            if (Swal.isVisible()) {
              Swal.update({
                text: `Waiting for ${data.waiting_count} more players to join...`
              });
            }
          }
        }
      })
      .catch(error => console.error('Error checking game status:', error));
  }, 2000);
  
  // Store the interval ID in sessionStorage so it persists across page refreshes
  sessionStorage.setItem('pollingIntervalId', interval);
  
  return interval;
}

// Handle voting to start a new game
function startNewGame() {
  // Mark this player as having voted
  sessionStorage.setItem('voted_for_restart', 'true');
  // Clear any previous decline flag to allow voting again
  sessionStorage.removeItem('restart_declined');
  console.log("Player voted to restart game");
  
  // Include session ID and username in request headers and body
  const options = {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Session-Id': sessionStorage.getItem('spotit_session_id') || ''
    },
    body: JSON.stringify({
      username: sessionStorage.getItem('spotit_username') || ''
    })
  };
  
  console.log("Sending restart request with options:", options);
  
  fetchWithSession('/request_restart', options)
    .then(res => res.json())
    .then(data => {
      console.log("Restart vote response:", data);
      
      // Handle error responses
      if (!data.success) {
        Swal.fire({
          icon: 'error',
          title: 'Restart Error',
          text: data.error || 'Could not request restart',
          timer: 5000,
          timerProgressBar: true
        });
        return;
      }
      
      if (data.restart_started) {
        // Show a more prominent restart notification
        showRestartCompletedNotification();
      } else if (data.success) {
        const requesters = data.requesters.join(', ');
        const initiator = data.restart_initiator || (data.requesters.length > 0 ? data.requesters[0] : "Someone");
        
        // For the initiator, show a more persistent notification
        const isInitiator = sessionStorage.getItem('spotit_username') === initiator;
        
        Swal.fire({
          toast: isInitiator ? false : true,
          position: 'top',
          icon: 'info',
          title: isInitiator ? 'Restart Request Sent' : `${data.vote_count}/${data.total_players} agreed to restart`,
          html: isInitiator 
            ? `You requested to restart the game.<br>Waiting for other players to agree.<br><b>${data.vote_count}/${data.total_players}</b> players have agreed.`
            : `${initiator} requested restart. Players who voted: ${requesters}`,
          // Keep notification visible until all votes are in
          timer: null,
          showConfirmButton: true,
          confirmButtonText: 'OK'
        });
      }
    })
    .catch(err => {
      console.error('Restart vote error:', err);
      // Try again with a simpler request
      fetch('/request_restart', { 
        method: 'POST',
        credentials: 'include'
      })
      .then(res => res.json())
      .then(data => console.log("Retry restart response:", data))
      .catch(err2 => console.error("Even simple restart failed:", err2));
    });
}

// Show a notification when restart is completed and all players have agreed
function showRestartCompletedNotification() {
  // Close any existing alerts
  Swal.close();
  
  // Show a more prominent restart notification
  Swal.fire({
    title: 'Game Restarting!',
    text: 'All players have agreed to restart. The game will refresh in a moment.',
    icon: 'success',
    timer: 3000,
    timerProgressBar: true,
    showConfirmButton: false,
    allowOutsideClick: false
  }).then(() => {
    console.log("Reloading page for game restart");
    window.location.href = '/'; // Go back to lobby
  });
}

// Show current restart vote status as a toast notification
function showVoteStatus(count, total, requesters, initiator) {
  const requestersText = requesters.join(', ');
  const initiatorText = initiator ? `${initiator} requested a restart.` : '';
  Swal.fire({
    toast: true,
    position: 'top',
    icon: 'info',
    title: `${count}/${total} agreed to restart`,
    text: `${initiatorText} Players who voted: ${requestersText}`,
    // Keep notification visible until all votes are in
    timer: count < total ? null : 3000,
    showConfirmButton: count < total
  });
}

// Show restart vote notification if present
function showRestartNotification(data) {
  // Check if there's an active restart vote
  if (data && data.restart_votes && data.restart_votes.length > 0) {
    const count = data.restart_votes.length;
    const total = data.total_players;
    const requesters = data.restart_requesters || [];
    const initiator = data.restart_initiator || (requesters.length > 0 ? requesters[0] : "Someone");
    const username = sessionStorage.getItem('spotit_username');
    
    console.log("Restart notification data:", {
      count, total, requesters, initiator, 
      username, voted: sessionStorage.getItem('voted_for_restart')
    });
    
    // If this player has already voted, just show the status
    if (sessionStorage.getItem('voted_for_restart') === 'true') {
      // Show vote status to the player who already voted
      showVoteStatus(count, total, requesters, initiator);
      return;
    }
    
    // If this player has already declined, don't show the dialog again
    if (sessionStorage.getItem('restart_declined') === 'true') {
      return;
    }
    
    // Don't show dialog if this player is the initiator (they already voted)
    if (username === initiator) {
      console.log("This player initiated the restart, showing status instead of prompt");
      sessionStorage.setItem('voted_for_restart', 'true');
      showVoteStatus(count, total, requesters, initiator);
      return;
    }
    
    // Prevent multiple dialogs
    if (restartDialogActive) {
      console.log("Restart dialog already active, not showing another");
      return;
    }
    
    restartDialogActive = true;
    
    // Show restart request to other players
    Swal.fire({
      title: 'Restart Game?',
      text: `${initiator} wants to start a new game. ${count}/${total} players have agreed.`,
      icon: 'question',
      showCancelButton: true,
      confirmButtonText: 'Yes, restart',
      cancelButtonText: 'No, continue',
      allowOutsideClick: false,
      allowEscapeKey: false
    }).then((result) => {
      restartDialogActive = false;
      
      if (result.isConfirmed) {
        // Mark this player as having voted
        sessionStorage.setItem('voted_for_restart', 'true');
        sessionStorage.removeItem('restart_declined');
        
        // Send restart vote
        startNewGame();
      } else {
        // Player declined restart
        console.log("Player declined restart");
        
        // Mark as declined to prevent showing the dialog again
        sessionStorage.setItem('restart_declined', 'true');
        
        // Send decline vote to server
        fetchWithSession('/decline_restart', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Session-Id': sessionStorage.getItem('spotit_session_id') || ''
          },
          body: JSON.stringify({
            username: sessionStorage.getItem('spotit_username') || ''
          })
        })
        .then(res => res.json())
        .then(data => {
          console.log("Restart decline response:", data);
          
          // Show a notification that the player declined
          Swal.fire({
            toast: true,
            position: 'top',
            icon: 'info',
            title: 'Restart Declined',
            text: `You declined to restart the game. The game will continue.`,
            timer: 3000,
            showConfirmButton: false
          });
        })
        .catch(err => console.error('Error declining restart:', err));
      }
    });
  } else if (data && data.restart_started) {
    // Game is restarting - all players agreed
    Swal.fire({
      title: 'Game Restarting!',
      text: 'All players have agreed to restart. The game will refresh in a moment.',
      icon: 'success',
      timer: 3000,
      timerProgressBar: true,
      showConfirmButton: false,
      allowOutsideClick: false
    }).then(() => {
      console.log("Reloading page for game restart");
      window.location.href = '/'; // Go back to lobby
    });
  } else if (data && data.restart_cancelled) {
    console.log("Restart was cancelled by a player");
    
    // Close any existing restart dialogs or notifications
    if (Swal.isVisible()) {
      const currentTitle = Swal.getTitle().textContent;
      if (currentTitle.includes('Restart') || currentTitle.includes('restart')) {
        Swal.close();
      }
    }
    
    // Only show the notification if we haven't shown it yet for this cancellation
    const cancelKey = `restart_cancelled_${data.declined_by || 'unknown'}`;
    if (!sessionStorage.getItem(cancelKey)) {
      sessionStorage.setItem(cancelKey, 'true');
      
      const username = sessionStorage.getItem('spotit_username');
      const initiator = data.restart_initiator;
      const isInitiator = username === initiator;
      
      // Show notification about restart being cancelled
      Swal.fire({
        toast: !isInitiator, // Full dialog for initiator, toast for others
        position: 'top',
        icon: 'info',
        title: isInitiator ? 'Your Restart Request was Declined' : 'Restart Cancelled',
        text: data.declined_by 
          ? `${data.declined_by} declined to restart. The game will continue.` 
          : 'A player declined to restart. The game will continue.',
        timer: isInitiator ? null : 5000,
        showConfirmButton: isInitiator
      });
      
      // Clear restart flags but keep track of who declined
      sessionStorage.removeItem('voted_for_restart');
      // Don't remove restart_declined here to prevent re-prompting the same player
    }
  }
}

// Track if a restart dialog is currently being shown
let restartDialogActive = false;

// Check if we're on the login page and initialize polling if needed
document.addEventListener('DOMContentLoaded', function() {
  // If we're on the login page
  if (document.getElementById('waiting-count')) {
    // Clear any stale sessionStorage data on login page
    sessionStorage.removeItem('spotit_username');
    sessionStorage.removeItem('spotit_session_id');
    
    // If we have URL parameters, check game status immediately
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('check_game_status') === 'true') {
      // Immediately check game status
      fetchWithSession('/check_game_status')
        .then(response => response.json())
        .then(data => {
          if (data.game_ready) {
            window.location.href = data.redirect;
          }
        });
    }
    
    // Start polling for game status automatically
    pollGameStatus();
  }
});

// Real-time polling: update cards and scores for all clients
if (document.getElementById('player-circle-container')) {
  setInterval(() => {
    fetchWithSession('/game_state')
      .then(response => response.json())
      .then(data => {
        const playerJson = JSON.stringify(data.player_emojis);
        const centerJson = JSON.stringify(data.center_emojis);
        if (playerJson !== lastPlayerData || centerJson !== lastCenterData) {
          // Clear highlights on new card state
          selectedPlayerEmoji = null;
          selectedCenterEmoji = null;
          clearHighlights();
          updateCard(data.center_emojis, data.player_emojis);
          lastPlayerData = playerJson;
          lastCenterData = centerJson;
        }
        updateScoreboard(data.names, data.scores);
        
        // Update restart button state based on cooldown
        updateRestartButton(data);
        
        // Check for restart_started first (highest priority)
        if (data.restart_started) {
          console.log("Game restart detected in game state - showing notification to all players");
          
          // Store that we've seen the restart notification to prevent showing it multiple times
          if (!sessionStorage.getItem('restart_notification_shown')) {
            sessionStorage.setItem('restart_notification_shown', 'true');
            
            // Show the restart notification
            showRestartCompletedNotification();
          }
          
          return; // Exit early to prevent other notifications
        }
        
        // Check for restart_cancelled flag (highest priority after restart_started)
        if (data.restart_cancelled) {
          console.log("Restart was cancelled by a player");
          
          // Close any existing restart dialogs or notifications
          if (Swal.isVisible()) {
            const currentTitle = Swal.getTitle().textContent;
            if (currentTitle.includes('Restart') || currentTitle.includes('restart')) {
              Swal.close();
            }
          }
          
          // Only show the notification if we haven't shown it yet for this cancellation
          const cancelKey = `restart_cancelled_${data.declined_by || 'unknown'}`;
          if (!sessionStorage.getItem(cancelKey)) {
            sessionStorage.setItem(cancelKey, 'true');
            
            const username = sessionStorage.getItem('spotit_username');
            const initiator = data.restart_initiator;
            const isInitiator = username === initiator;
            
            // Show notification about restart being cancelled
            Swal.fire({
              toast: !isInitiator, // Full dialog for initiator, toast for others
              position: 'top',
              icon: 'info',
              title: isInitiator ? 'Your Restart Request was Declined' : 'Restart Cancelled',
              text: data.declined_by 
                ? `${data.declined_by} declined to restart. The game will continue.` 
                : 'A player declined to restart. The game will continue.',
              timer: isInitiator ? null : 5000,
              showConfirmButton: isInitiator
            });
            
            // Clear restart flags but keep track of who declined
            sessionStorage.removeItem('voted_for_restart');
            // Don't remove restart_declined here to prevent re-prompting the same player
          }
          
          return; // Exit early to prevent other notifications
        }
        
        // Show restart vote notification if present
        if (data.restart_votes && (data.restart_votes.length > 0)) {
          // Update the initiator's notification if they're seeing it
          const username = sessionStorage.getItem('spotit_username');
          const initiator = data.restart_initiator;
          
          if (username === initiator && Swal.isVisible()) {
            const count = data.restart_votes.length;
            const total = data.total_players;
            
            // Update the vote count in the existing dialog
            const content = document.querySelector('.swal2-html-container');
            if (content) {
              content.innerHTML = `You requested to restart the game.<br>Waiting for other players to agree.<br><b>${count}/${total}</b> players have agreed.`;
            }
          } else {
            // Show or update restart notification for other players
            showRestartNotification(data);
          }
        } else {
          // Clear restart vote flag when no votes are active
          if (data.restart_votes && data.restart_votes.length === 0) {
            // Only clear these flags if there are no active votes
            // This allows players to vote again for a new restart
            sessionStorage.removeItem('voted_for_restart');
            sessionStorage.removeItem('restart_notification_shown');
            
            // Clear all restart_cancelled_* keys
            Object.keys(sessionStorage).forEach(key => {
              if (key.startsWith('restart_cancelled_')) {
                sessionStorage.removeItem(key);
              }
            });
            
            restartDialogActive = false;
          }
        }
      })
      .catch(error => console.error('Polling error:', error));
  }, 1000);
}

// Add a new function to handle the restart button UI based on cooldown
function updateRestartButton(data) {
  const restartButton = document.getElementById('restart-button');
  if (!restartButton) return;
  
  // Check if there's a cooldown period active
  if (data && data.cooldown_remaining && data.cooldown_remaining > 0) {
    restartButton.disabled = true;
    restartButton.textContent = `Start New Game (${data.cooldown_remaining}s)`;
    
    // If we haven't set a timer yet for this cooldown, set one now
    if (!window.restartCooldownTimer) {
      window.restartCooldownTimer = setInterval(() => {
        const newText = restartButton.textContent;
        const match = newText.match(/\((\d+)s\)/);
        if (match) {
          const seconds = parseInt(match[1]);
          if (seconds > 1) {
            restartButton.textContent = `Start New Game (${seconds-1}s)`;
          } else {
            restartButton.disabled = false;
            restartButton.textContent = 'Start New Game';
            clearInterval(window.restartCooldownTimer);
            window.restartCooldownTimer = null;
          }
        }
      }, 1000);
    }
  } else {
    // No cooldown, enable the button
    if (window.restartCooldownTimer) {
      clearInterval(window.restartCooldownTimer);
      window.restartCooldownTimer = null;
    }
    restartButton.disabled = false;
    restartButton.textContent = 'Start New Game';
  }
}

// Add event handlers for all fetch calls to include credentials and custom session id header for multi-client support
function fetchWithSession(url, options = {}) {
  // Ensure options and headers exist
  options = options || {};
  options.headers = options.headers || {};
  
  // Always include credentials
  options.credentials = 'include';
  
  // Get session ID from URL or sessionStorage
  const urlParams = new URLSearchParams(window.location.search);
  const sessionId = urlParams.get('session_id') || sessionStorage.getItem('spotit_session_id');
  
  if (sessionId) {
    // Add session ID to headers
    options.headers['X-Session-Id'] = sessionId;
    
    // Add session ID to URL if not already in URL
    if (!url.includes('session_id=')) {
      url += (url.includes('?') ? '&' : '?') + 'session_id=' + sessionId;
    }
  }
  
  // Add username to headers if available
  const username = sessionStorage.getItem('spotit_username');
  if (username) {
    options.headers['X-Username'] = username;
  }
  
  console.log(`Fetch with session: ${url}`, options);
  
  return fetch(url, options);
}

// Arrange the emojis once the page loads
window.onload = arrangeEmojiForAll;

// When a username is submitted
document.addEventListener('DOMContentLoaded', function() {
  const usernameForm = document.getElementById('username-form');
  if (usernameForm) {
    usernameForm.addEventListener('submit', function(e) {
      e.preventDefault();
      const username = document.getElementById('username').value;
      
      // Store in sessionStorage for later use
      sessionStorage.setItem('spotit_username', username);
      console.log("Stored username in sessionStorage:", username);
      
      fetch('/set_username', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ username: username }),
        credentials: 'include'  // Include cookies
      })
      .then(response => response.json())
      .then(data => {
        console.log("Username submission response:", data);
        if (data.success) {
          // Store session ID for restart requests
          if (data.session_id) {
            sessionStorage.setItem('spotit_session_id', data.session_id);
            console.log("Stored session ID in sessionStorage:", data.session_id);
          }
          
          if (data.username) {
            sessionStorage.setItem('spotit_username', data.username);
            console.log("Stored username in sessionStorage:", data.username);
          }
          
          if (data.redirect) {
            // Append session ID to URL if not already there
            let redirectUrl = data.redirect;
            if (!redirectUrl.includes('session_id=') && data.session_id) {
              redirectUrl += (redirectUrl.includes('?') ? '&' : '?') + 'session_id=' + data.session_id;
            }
            console.log("Redirecting to game with session ID:", redirectUrl);
            window.location.href = redirectUrl;
          } else {
            document.getElementById('waiting-message').style.display = 'block';
            document.getElementById('username-form').style.display = 'none';
            
            // Start polling for game status
            pollGameStatus();
          }
        } else {
          // Show error message
          Swal.fire({
            title: 'Error',
            text: data.error,
            icon: 'error',
            confirmButtonText: 'Try Again'
          }).then(() => {
            promptUsername();
          });
        }
      })
      .catch(err => {
        console.error("Error submitting username:", err);
        alert("Error submitting username. Please try again.");
      });
    });
  }
});