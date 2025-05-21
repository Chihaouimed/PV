{
    'name': 'PV Reporting',
    'version': '1.0',
    'summary': 'Reporting et analyse BI pour la gestion PV',
    'description': """
        Module de reporting et d'analyse pour la gestion des installations PV.
        Fournit des tableaux de bord, graphiques, vues pivot et analyses statistiques
        pour mieux comprendre les performances des installations, interventions et réclamations.
    """,
    'author': 'Chihaoui Mohamed',
    'category': 'Reporting',
    'depends': [
        'base',
        'mail',
        'pv_management',
        'web',
        'board',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/pv_installation_report_views.xml',
        'views/pv_intervention_report_views.xml',
        'views/pv_reclamation_report_views.xml',
        'views/pv_dashboard_views.xml',
        'views/menu_views.xml',

    ],
    'external_dependencies': {
        'python': ['requests', 'json'],
    },

    'qweb': [],
    'application': True,
    'installable': True,
    'auto_install': False,
}
