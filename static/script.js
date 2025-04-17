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
  fetch(addr, {
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
  fetch('/shuffle', {
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
  fetch('/rotate', {
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

function start_new_game() {
  fetch('/start_new_game', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  })
    .then(response => response.json())
    .then(data => {
      if (data.redirect_url) {
        window.location.href = data.redirect_url;
      }
    });
}

function promptUsername() {
  Swal.fire({
    title: 'Enter your username',
    input: 'text',
    inputPlaceholder: 'Username',
    confirmButtonText: 'Join',
    showCancelButton: true,
    inputValidator: (value) => {
      if (!value) {
        return 'Username is required!';
      }
    }
  }).then((result) => {
    if (result.isConfirmed) {
      const username = result.value;

      fetch('/set_username', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username })
      });

      // Then go to game
      // start_new_game();
    }
  });
}




// Arrange the emojis once the page loads
window.onload = arrangeEmojiForAll;