const sidebarToggle = document.querySelector('#sidebar-toggle');
const clusterSection = document.querySelector('[data-sidebar-section="clusters"]');
const collapsedKey = 'cluster-builder-sidebar-collapsed';
const clustersOpenKey = 'cluster-builder-clusters-open';

const setCollapsed = collapsed => {
  document.body.classList.toggle('sidebar-collapsed', collapsed);
  if (sidebarToggle) {
    sidebarToggle.setAttribute('aria-pressed', String(collapsed));
    sidebarToggle.setAttribute('aria-label', collapsed ? 'Sidebar ausklappen' : 'Sidebar einklappen');
  }
};

setCollapsed(localStorage.getItem(collapsedKey) === '1');

if (clusterSection) {
  const storedOpen = localStorage.getItem(clustersOpenKey);
  if (storedOpen !== null) clusterSection.open = storedOpen === '1';
  clusterSection.addEventListener('toggle', () => {
    localStorage.setItem(clustersOpenKey, clusterSection.open ? '1' : '0');
  });
}

sidebarToggle?.addEventListener('click', () => {
  const collapsed = !document.body.classList.contains('sidebar-collapsed');
  setCollapsed(collapsed);
  localStorage.setItem(collapsedKey, collapsed ? '1' : '0');
});
