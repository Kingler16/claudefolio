/* Velora chart theme: live CSS-token readers + palette for Chart.js / TradingView. */
(function() {
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const isDark = () => window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;

  window.VeloraChartTheme = {
    colors: ['#22d3ee','#10b981','#3b82f6','#06b6d4','#34d399','#0891b2','#a7f3d0','#fbbf24','#f472b6'],
    bg:          () => css('--bg-canvas'),
    bodyBg:      () => css('--bg-body'),
    text:        () => css('--text-secondary'),
    textPrimary: () => css('--text-primary'),
    textMuted:   () => css('--text-muted'),
    accent:      () => css('--accent'),
    accentBg:    () => css('--accent-bg'),
    grid:        () => isDark() ? 'rgba(255,255,255,0.06)' : 'rgba(10,20,40,0.08)',
    border:      () => isDark() ? 'rgba(255,255,255,0.10)' : 'rgba(10,20,40,0.10)',
    tooltipBg:   () => isDark() ? 'rgba(10,15,31,0.92)' : 'rgba(255,255,255,0.95)',
    tooltipBorder: () => isDark() ? 'rgba(255,255,255,0.12)' : 'rgba(10,20,40,0.10)',
    green:       () => css('--green'),
    red:         () => css('--red'),
    yellow:      () => css('--yellow'),
  };
})();
