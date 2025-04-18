function arrangeEmojiForAll() {
  arrangeEmoji('player-circle-container');
  arrangeEmoji('center-circle-container');
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
}

function clearHighlights() {
  document.querySelectorAll('.emoji.highlighted').forEach(el => {
    el.classList.remove('highlighted');
  });
}

function highlightEmoji(containerId, emojiChar) {
  document.getElementById(containerId).querySelectorAll('.emoji').forEach(el => {
    if (el.textContent.trim() === emojiChar) {
      el.classList.add('highlighted');
    }
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
      if (data && data.highlight) {
        clearHighlights();
        highlightEmoji(containerId, data.highlight);
      }
      if (data && data.clear_highlight) {
        clearHighlights();
      }
      if (data && data.names && data.scores) { // update scoreboard
        updateScoreboard(data.names, data.scores)
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
      else if (data && data.center_emojis && data.player_emojis && data.clear_highlight) {
        Swal.fire({
          title: "Shuffled",
          icon: "success",
          scrollbarPadding: false
        });
        clearHighlights();
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
      
      // Store username in localStorage for persistence
      localStorage.setItem('spotit_username', username);
      
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
          // Store session info in localStorage
          if (data.session_id) {
            localStorage.setItem('spotit_session_id', data.session_id);
            console.log('Stored session ID:', data.session_id);
          }
          
          if (data.username) {
            localStorage.setItem('spotit_username', data.username);
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
      .catch(error => {
        console.error('Error checking game status:', error);
      });
  }, 2000);
  
  // Store the interval ID in localStorage so it persists across page refreshes
  localStorage.setItem('pollingIntervalId', interval);
  
  return interval;
}

// Check if we're on the login page and initialize polling if needed
document.addEventListener('DOMContentLoaded', function() {
  // If we're on the login page
  if (document.getElementById('waiting-count')) {
    // Check if we already have a stored username
    const storedUsername = localStorage.getItem('spotit_username');
    const storedSessionId = localStorage.getItem('spotit_session_id');
    
    console.log('Stored username:', storedUsername);
    console.log('Stored session ID:', storedSessionId);
    
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

// Add event handlers for all fetch calls to include credentials
function fetchWithSession(url, options = {}) {
  // Always include credentials
  const sessionOptions = {
    ...options,
    credentials: 'include'
  };
  
  return fetch(url, sessionOptions);
}

// Arrange the emojis once the page loads
window.onload = arrangeEmojiForAll;