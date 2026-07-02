{
    'name': "DSA",

    'summary': "Implementation for DSA Sheet",

    'description': """
Long description of module's purpose
    """,

    'author': "RaazDk",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',
    'application': True,
    'installable': True,

    # any module necessary for this one to work correctly
    'depends': ['base','hr'],


 ## Loading of assets
    'assets':{
        'web.assets_backend':[
            'dsa/static/styles/dsa_styles.css'
        ],
    },


    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/reports/claimsheet.xml',
        'views/dsa_details.xml',
        'views/dsa_configurations.xml',
        'views/menu_items.xml',


    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}

