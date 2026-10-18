"""Modèle HTML des rapports (Jinja2, échappement automatique activé)."""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EchoTrace - Rapport d'analyse OSINT</title>
<style>
body { font-family: system-ui, "Segoe UI", Roboto, sans-serif; line-height: 1.6; margin: 0;
       padding: 20px; background: #f5f5f5; color: #333; }
.container { max-width: 1200px; margin: 0 auto; background: #fff; padding: 30px;
             border-radius: 10px; box-shadow: 0 0 20px rgba(0,0,0,.1); }
.header { text-align: center; border-bottom: 3px solid #007bff; padding-bottom: 20px; margin-bottom: 30px; }
.header h1 { color: #007bff; margin: 0; font-size: 2.2em; }
.subtitle { color: #666; }
h2 { color: #007bff; border-bottom: 2px solid #eee; padding-bottom: 10px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 15px; }
.item { background: #f8f9fa; padding: 12px 15px; border-radius: 5px; border-left: 4px solid #007bff;
        overflow-wrap: anywhere; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 20px; }
.card { background: linear-gradient(135deg, #007bff, #0056b3); color: #fff; padding: 20px;
        border-radius: 10px; text-align: center; }
.card b { display: block; font-size: 2em; }
table { width: 100%; border-collapse: collapse; margin-top: 20px; }
th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; overflow-wrap: anywhere; }
th { background: #007bff; color: #fff; }
.high { background: #d4edda; color: #155724; padding: 2px 8px; border-radius: 10px; }
.medium { background: #fff3cd; color: #856404; padding: 2px 8px; border-radius: 10px; }
.low { background: #f8d7da; color: #721c24; padding: 2px 8px; border-radius: 10px; }
.notice { background: #fff3cd; border: 1px solid #ffeaa7; color: #856404; padding: 15px;
          border-radius: 5px; margin: 20px 0; }
.footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center;
          color: #666; font-size: .9em; }
.graph { text-align: center; color: #333; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>EchoTrace</h1>
    <div class="subtitle">Rapport d'analyse OSINT - données publiques uniquement</div>
    <div class="subtitle">Généré le {{ generation_time }}</div>
  </div>

  <h2>Informations sur la cible</h2>
  {% if purpose %}<div class="item" style="margin-bottom:15px"><strong>Finalité de la recherche :</strong> {{ purpose }}</div>{% endif %}
  <div class="grid">
    {% for key, value in target_data.items() if value %}
    <div class="item"><strong>{{ key|title }} :</strong> {{ value }}</div>
    {% endfor %}
  </div>

  <h2>Résumé</h2>
  <div class="cards">
    <div class="card"><b>{{ summary.total }}</b>Résultats</div>
    <div class="card"><b>{{ summary.high_confidence }}</b>Haute confiance</div>
    <div class="card"><b>{{ summary.platforms|length }}</b>Plateformes</div>
    <div class="card"><b>{{ "%.1f"|format(summary.avg_confidence * 100) }}%</b>Confiance moyenne</div>
  </div>

  {% if graph_svg %}
  <h2>Graphe de corrélation</h2>
  <div class="graph">{{ graph_svg|safe }}</div>
  {% endif %}

  <h2>Résultats détaillés</h2>
  <table>
    <thead><tr><th>Plateforme</th><th>Confiance</th><th>URL</th><th>Titre</th><th>Pseudo</th><th>Indices</th><th>Statut</th><th>Note</th></tr></thead>
    <tbody>
    {% for r in results %}
    <tr>
      <td>{{ r.platform }}</td>
      <td><span class="{{ 'high' if r.confidence >= 0.8 else ('medium' if r.confidence >= 0.5 else 'low') }}">{{ "%.0f"|format(r.confidence * 100) }}%</span></td>
      <td>{% if r.url.startswith(('http://', 'https://')) %}<a href="{{ r.url }}" target="_blank" rel="noopener noreferrer">{{ r.url }}</a>{% else %}-{% endif %}</td>
      <td>{{ r.title }}</td>
      <td>{{ r.username or '-' }}</td>
      <td>{% if r.data and r.data.signals %}{{ r.data.signals|join(', ') }}{% elif r.data and r.data.verifiable == false %}profil non vérifiable{% else %}-{% endif %}</td>
      <td>{{ status_labels.get(r.status, '') or '-' }}</td>
      <td>{{ r.note or '-' }}</td>
    </tr>
    {% endfor %}
    </tbody>
  </table>

  <div class="notice">
    <strong>Avertissement :</strong> ce rapport ne contient que des informations issues de sources publiques.
    Leur usage doit respecter les lois applicables sur la protection des données et de la vie privée.
    Un résultat n'est pas une preuve d'identité : vérifiez-le avant de vous y fier.
    Données personnelles : conservez ce rapport le temps nécessaire à la finalité indiquée, puis supprimez-le.
  </div>
  <div class="footer">EchoTrace - Données publiques uniquement</div>
</div>
</body>
</html>
"""
