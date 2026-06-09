const slider = document.getElementById('angle');
const real = document.getElementById('real');
const decoy = document.getElementById('decoy');
const status = document.getElementById('status');

slider.oninput = (e) => {
  const angle = Math.abs(e.target.value);
  const opacity = Math.min(1, Math.max(0, (angle - 12) / 10)); // Transition between 12 and 22 degrees
  
  real.style.opacity = 1 - opacity;
  decoy.style.opacity = opacity;
  
  if (angle > 15) {
    status.textContent = '❌ OUT OF ZONE: Decoy Visible';
    status.style.background = '#ef4444';
  } else {
    status.textContent = '✅ ALIGNED: Real Question Visible';
    status.style.background = '#10b981';
  }
};

document.getElementById('tryLiveBtn').onclick = () => {
  location.href = 'index.html';
};
