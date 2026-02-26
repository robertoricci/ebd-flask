from datetime import date

def register(app):
    @app.template_filter('fmt_date')
    def fmt_date(d):
        if not d:
            return '-'
        if isinstance(d, str):
            return d
        return d.strftime('%d/%m/%Y')

    @app.template_filter('fmt_currency')
    def fmt_currency(v):
        if v is None:
            return 'R$ 0,00'
        return f'R$ {v:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')

    @app.template_filter('status_badge')
    def status_badge(s):
        colors = {'ABERTO': 'badge-blue', 'LIBERADO': 'badge-yellow', 'FINALIZADO': 'badge-green'}
        return colors.get(s, 'badge-gray')

    @app.template_filter('pct_color')
    def pct_color(v):
        if v is None:
            return '#ef4444'
        try:
            v = float(v)
        except (TypeError, ValueError):
            return '#ef4444'
        if v >= 75: return '#10b981'
        if v >= 50: return '#f59e0b'
        return '#ef4444'

    @app.context_processor
    def inject_globals():
        return dict(today=date.today())

    app.jinja_env.globals['enumerate'] = enumerate
