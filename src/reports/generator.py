"""
EchoTrace — Report Generator
Génération de rapports HTML et PDF
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Optional
from jinja2 import Template
import base64

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    plt = None

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    nx = None

try:
    from pyvis.network import Network
    PYVIS_AVAILABLE = True
except ImportError:
    PYVIS_AVAILABLE = False
    Network = None


class ReportGenerator:
    """Générateur de rapports pour EchoTrace."""
    
    def __init__(self, output_dir: str = "exports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def generate_html_report(self, target_data: Dict, results: List[Dict], 
                           analysis_summary: Dict, filename: Optional[str] = None) -> str:
        """Génère un rapport HTML."""
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"echotrace_report_{timestamp}.html"
        
        filepath = os.path.join(self.output_dir, filename)
        
        # Template HTML
        html_template = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EchoTrace - Rapport d'Analyse OSINT</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
            color: #333;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }
        .header {
            text-align: center;
            border-bottom: 3px solid #007bff;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        .header h1 {
            color: #007bff;
            margin: 0;
            font-size: 2.5em;
        }
        .header .subtitle {
            color: #666;
            font-size: 1.1em;
            margin-top: 5px;
        }
        .section {
            margin-bottom: 30px;
        }
        .section h2 {
            color: #007bff;
            border-bottom: 2px solid #eee;
            padding-bottom: 10px;
        }
        .target-info {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .target-info h3 {
            margin-top: 0;
            color: #495057;
        }
        .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
        }
        .info-item {
            background: white;
            padding: 15px;
            border-radius: 5px;
            border-left: 4px solid #007bff;
        }
        .info-item strong {
            color: #007bff;
        }
        .summary-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .summary-card {
            background: linear-gradient(135deg, #007bff, #0056b3);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
        }
        .summary-card h3 {
            margin: 0;
            font-size: 2em;
        }
        .summary-card p {
            margin: 5px 0 0 0;
            opacity: 0.9;
        }
        .results-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        .results-table th,
        .results-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        .results-table th {
            background-color: #007bff;
            color: white;
            font-weight: bold;
        }
        .results-table tr:hover {
            background-color: #f5f5f5;
        }
        .confidence-high {
            background-color: #d4edda;
            color: #155724;
        }
        .confidence-medium {
            background-color: #fff3cd;
            color: #856404;
        }
        .confidence-low {
            background-color: #f8d7da;
            color: #721c24;
        }
        .platform-badge {
            background-color: #6c757d;
            color: white;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: bold;
        }
        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            text-align: center;
            color: #666;
            font-size: 0.9em;
        }
        .graph-container {
            margin: 20px 0;
            text-align: center;
        }
        .warning {
            background-color: #fff3cd;
            border: 1px solid #ffeaa7;
            color: #856404;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }
        .disclaimer {
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            color: #6c757d;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 EchoTrace</h1>
            <div class="subtitle">Rapport d'Analyse OSINT - Données Publiques Uniquement</div>
            <div class="subtitle">Généré le {{ generation_time }}</div>
        </div>

        <div class="section">
            <h2>📋 Informations sur la Cible</h2>
            <div class="target-info">
                <h3>Données d'Entrée</h3>
                <div class="info-grid">
                    {% for key, value in target_data.items() %}
                    {% if value %}
                    <div class="info-item">
                        <strong>{{ key|title }}:</strong> {{ value }}
                    </div>
                    {% endif %}
                    {% endfor %}
                </div>
            </div>
        </div>

        <div class="section">
            <h2>📊 Résumé de l'Analyse</h2>
            <div class="summary-cards">
                <div class="summary-card">
                    <h3>{{ analysis_summary.total }}</h3>
                    <p>Résultats trouvés</p>
                </div>
                <div class="summary-card">
                    <h3>{{ analysis_summary.high_confidence }}</h3>
                    <p>Haute confiance</p>
                </div>
                <div class="summary-card">
                    <h3>{{ analysis_summary.platforms|length }}</h3>
                    <p>Plateformes</p>
                </div>
                <div class="summary-card">
                    <h3>{{ "%.1f"|format(analysis_summary.avg_confidence * 100) }}%</h3>
                    <p>Confiance moyenne</p>
                </div>
            </div>
        </div>

        {% if analysis_summary.platforms %}
        <div class="section">
            <h2>🌐 Plateformes Identifiées</h2>
            <div class="info-grid">
                {% for platform, count in analysis_summary.platforms %}
                <div class="info-item">
                    <strong>{{ platform }}:</strong> {{ count }} résultat(s)
                </div>
                {% endfor %}
            </div>
        </div>
        {% endif %}

        <div class="section">
            <h2>📋 Résultats Détaillés</h2>
            <table class="results-table">
                <thead>
                    <tr>
                        <th>Plateforme</th>
                        <th>Confiance</th>
                        <th>URL</th>
                        <th>Titre</th>
                        <th>Username</th>
                        <th>Module</th>
                    </tr>
                </thead>
                <tbody>
                    {% for result in results %}
                    <tr>
                        <td><span class="platform-badge">{{ result.platform }}</span></td>
                        <td>
                            {% set confidence_class = "confidence-high" if result.confidence >= 0.8 else ("confidence-medium" if result.confidence >= 0.5 else "confidence-low") %}
                            <span class="{{ confidence_class }}">
                                {{ "%.1f"|format(result.confidence * 100) }}%
                            </span>
                        </td>
                        <td><a href="{{ result.url }}" target="_blank">{{ result.url[:50] }}{% if result.url|length > 50 %}...{% endif %}</a></td>
                        <td>{{ result.title }}</td>
                        <td>{{ result.username or '-' }}</td>
                        <td>{{ result.module }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <div class="warning">
            <strong>⚠️ Avertissement Important:</strong> Ce rapport contient des informations collectées à partir de sources publiques uniquement. 
            L'utilisation de ces informations doit respecter les lois locales et internationales applicables à la protection des données et à la vie privée.
        </div>

        <div class="disclaimer">
            <strong>Disclaimer:</strong> EchoTrace est un outil d'analyse OSINT destiné à des fins légales et éthiques uniquement. 
            Les utilisateurs sont responsables de s'assurer que leurs activités de recherche respectent toutes les lois et réglementations applicables. 
            Cet outil ne doit pas être utilisé pour des activités illégales, le harcèlement, ou la violation de la vie privée.
        </div>

        <div class="footer">
            <p>Generated by EchoTrace - OSINT Correlation Engine</p>
            <p>Public Data Only • Legal Research • No Hacking • No Private Access</p>
        </div>
    </div>
</body>
</html>
        """
        
        # Rendre le template
        template = Template(html_template)
        html_content = template.render(
            generation_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            target_data=target_data,
            results=results,
            analysis_summary=analysis_summary
        )
        
        # Sauvegarder le fichier
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return filepath
    
    def generate_json_report(self, target_data: Dict, results: List[Dict], 
                           analysis_summary: Dict, filename: Optional[str] = None) -> str:
        """Génère un rapport JSON."""
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"echotrace_report_{timestamp}.json"
        
        filepath = os.path.join(self_dir, filename)
        
        report_data = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "tool": "EchoTrace",
                "version": "1.0.0",
                "description": "OSINT Analysis Report - Public Data Only"
            },
            "target": target_data,
            "summary": analysis_summary,
            "results": results,
            "statistics": {
                "total_results": len(results),
                "high_confidence_count": len([r for r in results if r.get('confidence', 0) >= 0.8]),
                "medium_confidence_count": len([r for r in results if 0.5 <= r.get('confidence', 0) < 0.8]),
                "low_confidence_count": len([r for r in results if r.get('confidence', 0) < 0.5]),
                "platforms_found": list(set(r.get('platform', '') for r in results if r.get('platform'))),
                "modules_used": list(set(r.get('module', '') for r in results if r.get('module')))
            }
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        return filepath
    
    def generate_network_graph(self, results: List[Dict], filename: Optional[str] = None) -> str:
        """Génère un graphe de corrélation réseau."""
        
        if not NETWORKX_AVAILABLE or not PYVIS_AVAILABLE:
            print("NetworkX ou Pyvis non disponible - génération de graphe ignorée")
            return ""
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"echotrace_network_{timestamp}.html"
        
        filepath = os.path.join(self.output_dir, filename)
        
        # Créer le graphe
        G = nx.Graph()
        
        # Ajouter les nœuds et arêtes
        for result in results:
            platform = result.get('platform', '')
            username = result.get('username', '')
            url = result.get('url', '')
            
            if platform:
                G.add_node(platform, type='platform', size=20)
            
            if username:
                G.add_node(username, type='username', size=15)
                if platform:
                    G.add_edge(username, platform, weight=result.get('confidence', 0))
        
        # Créer le graphe interactif avec pyvis
        net = Network(height="600px", width="100%", bgcolor="#222222", font_color="white")
        
        # Ajouter les nœuds
        for node in G.nodes():
            node_type = G.nodes[node].get('type', 'unknown')
            color = '#007bff' if node_type == 'platform' else '#28a745'
            size = G.nodes[node].get('size', 10)
            
            net.add_node(node, label=node, color=color, size=size)
        
        # Ajouter les arêtes
        for edge in G.edges():
            weight = G.edges[edge].get('weight', 0.5)
            net.add_edge(edge[0], edge[1], weight=weight)
        
        # Configurer les options
        net.set_options("""
        {
          "nodes": {
            "borderWidth": 2,
            "borderWidthSelected": 4
          },
          "edges": {
            "color": {
              "inherit": true
            },
            "smooth": {
              "type": "continuous"
            }
          },
          "physics": {
            "barnesHut": {
              "gravitationalConstant": -8000,
              "centralGravity": 0.3,
              "springLength": 95,
              "springConstant": 0.04,
              "damping": 0.09,
              "avoidOverlap": 0.1
            }
          },
          "interaction": {
            "hover": true,
            "tooltipDelay": 200,
            "hideEdgesOnDrag": true
          }
        }
        """)
        
        # Sauvegarder le graphe
        net.save_graph(filepath)
        
        return filepath
