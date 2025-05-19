from odoo import models, fields, api

class AlarmManagement(models.Model):
    _name = 'alarm.management'
    _description = 'Alarm Management'

    name = fields.Char(string='Name', required=True, translate=True)
    partie = fields.Selection([
        ('onduleur', 'Onduleur'),
        ('module', 'Module'),
        ('installation', 'Installation'),
        ('batterie', 'Batterie'),
        ('autre', 'Autre')
    ], string='Partie', required=True, translate=True)
    marque_onduleur_id = fields.Many2one('marque.onduleur', string='Marque Onduleur')
    code_alarm = fields.Char(string='Code Alarm', required=True, translate=True)

    @api.onchange('partie')
    def _onchange_partie(self):
        # Clear the marque_onduleur_id when partie is not 'onduleur'
        if self.partie != 'onduleur':
            self.marque_onduleur_id = False


