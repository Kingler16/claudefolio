/* Velora chart theme: live CSS-token readers + responsive helpers + Apex defaults. */
(function() {
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const isDark = () => window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;

  window.VeloraChartTheme = {
    colors: ['#22d3ee', '#6366f1', '#3b82f6', '#8b5cf6', '#fbbf24', '#0891b2', '#f472b6', '#94a3b8', '#f87171'],
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
    green:       () => css('--gain'),
    red:         () => css('--loss'),
    yellow:      () => css('--warn'),
  };

  // Drei Stufen, identisch zur CSS-Breakpoint-Logik in responsive.css.
  const isPhone   = () => window.matchMedia && window.matchMedia('(max-width: 767.98px)').matches;
  const isTablet  = () => window.matchMedia && window.matchMedia('(min-width: 768px) and (max-width: 1023.98px)').matches;
  const isDesktop = () => window.matchMedia && window.matchMedia('(min-width: 1024px)').matches;
  const screenSize = () => isPhone() ? 'phone' : isTablet() ? 'tablet' : 'desktop';

  // Chart-Heights synchron zu .chart-h-{sm,md,lg} in responsive.css.
  // Gut, dass JS (ApexCharts.chart.height) und CSS-Klassen denselben Wert liefern.
  const HEIGHTS = {
    sm: { phone: 200, tablet: 240, desktop: 260 },
    md: { phone: 240, tablet: 300, desktop: 340 },
    lg: { phone: 280, tablet: 360, desktop: 420 },
  };
  const chartHeight = (size) => (HEIGHTS[size] || HEIGHTS.md)[screenSize()];

  window.VeloraApex = {
    baseOptions() {
      const dark = isDark();
      const phone = isPhone();
      const tablet = isTablet();
      const compact = phone || tablet;
      return {
        chart: {
          foreColor: window.VeloraChartTheme.text(),
          toolbar: { show: false },
          fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif',
          background: 'transparent',
          width: '100%',
          // Mobile/Tablet: Animationen reduzieren (weniger GPU-Last, schnelleres Initial-Paint).
          animations: phone ? {
            enabled: false,
          } : {
            enabled: true,
            easing: 'easeout',
            speed: tablet ? 400 : 600,
            animateGradually: { enabled: !tablet, delay: 80 },
          },
          redrawOnWindowResize: true,
          redrawOnParentResize: true,
        },
        theme: { mode: dark ? 'dark' : 'light' },
        grid: {
          borderColor: window.VeloraChartTheme.grid(),
          strokeDashArray: 4,
          xaxis: { lines: { show: false } },
          padding: phone ? { left: 4, right: 4, top: 0, bottom: 0 }
                  : tablet ? { left: 8, right: 8, top: 0, bottom: 0 }
                  : undefined,
        },
        tooltip: {
          theme: dark ? 'dark' : 'light',
          style: { fontSize: phone ? '11px' : '12px', fontFamily: 'Inter' },
          marker: { show: true },
        },
        colors: window.VeloraChartTheme.colors,
        dataLabels: { enabled: false },
        legend: {
          labels: { colors: window.VeloraChartTheme.text() },
          fontFamily: 'Inter',
          fontSize: phone ? '10px' : tablet ? '11px' : '12px',
          markers: { width: phone ? 8 : 10, height: phone ? 8 : 10 },
          itemMargin: compact ? { horizontal: 6, vertical: 2 } : undefined,
          position: phone ? 'bottom' : undefined,
        },
        stroke: {
          // Phone: gerade Linien (CPU-schonender, schärfer auf 375px).
          curve: phone ? 'straight' : 'smooth',
          width: 2,
        },
        // Mehrstufige Responsive-Konfiguration. Wirkt zusätzlich zu den isPhone()-
        // Defaults oben, falls Chart auf eigene Breakpoints zugeschnitten ist.
        responsive: [
          {
            breakpoint: 1024,
            options: {
              legend: { fontSize: '11px' },
            },
          },
          {
            breakpoint: 768,
            options: {
              chart: { height: 240 },
              stroke: { curve: 'straight' },
              legend: { fontSize: '10px', position: 'bottom', markers: { width: 8, height: 8 } },
              plotOptions: { pie: { donut: { size: '60%' }, expandOnClick: false } },
            },
          },
        ],
      };
    },
    // Donut-/Pie-Defaults: Phone zeigt dataLabels (sonst keine % sichtbar),
    // expandOnClick auf Phone deaktiviert (Touch-Tap-Konflikt).
    donutDefaults() {
      const phone = isPhone();
      return {
        plotOptions: {
          pie: {
            donut: { size: phone ? '58%' : '65%' },
            expandOnClick: !phone,
          },
        },
        dataLabels: {
          enabled: phone,
          style: { fontSize: phone ? '10px' : '11px', fontFamily: 'Inter', fontWeight: 600 },
          dropShadow: { enabled: false },
        },
      };
    },
    // Labels auf Phone kürzen (Donut-Legenden bleiben so lesbar).
    truncateLabels(labels, max) {
      if (!isPhone()) return labels;
      const limit = max || 18;
      return labels.map(l => (typeof l === 'string' && l.length > limit) ? l.slice(0, limit - 1) + '…' : l);
    },
    chartHeight,
    screenSize,
    isMobile: isPhone,    // Backwards-compat alias
    isPhone,
    isTablet,
    isDesktop,
  };
})();
