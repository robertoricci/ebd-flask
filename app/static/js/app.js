// Modal helpers
function openModal(id){ document.getElementById(id).style.display='flex'; }
function closeModal(id){ document.getElementById(id).style.display='none'; }

// Search filter for tables
function searchTable(inputId, tableId){
  const q = document.getElementById(inputId).value.toLowerCase();
  document.querySelectorAll(`#${tableId} tbody tr`).forEach(tr=>{
    tr.style.display = tr.textContent.toLowerCase().includes(q) ? '' : 'none';
  });
}

// Close modal on Escape
document.addEventListener('keydown', e=>{
  if(e.key==='Escape') document.querySelectorAll('.modal-overlay').forEach(m=>m.style.display='none');
});

// Auto-hide alerts after 4s
document.addEventListener('DOMContentLoaded', ()=>{
  document.querySelectorAll('.alert').forEach(a=>{
    setTimeout(()=>{ a.style.transition='opacity .5s'; a.style.opacity='0';
      setTimeout(()=>a.remove(),500); }, 4000);
  });
});
