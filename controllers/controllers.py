# from odoo import http


# class Customaddons\dsa(http.Controller):
#     @http.route('/customaddons\dsa/customaddons\dsa', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/customaddons\dsa/customaddons\dsa/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('customaddons\dsa.listing', {
#             'root': '/customaddons\dsa/customaddons\dsa',
#             'objects': http.request.env['customaddons\dsa.customaddons\dsa'].search([]),
#         })

#     @http.route('/customaddons\dsa/customaddons\dsa/objects/<model("customaddons\dsa.customaddons\dsa"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('customaddons\dsa.object', {
#             'object': obj
#         })

