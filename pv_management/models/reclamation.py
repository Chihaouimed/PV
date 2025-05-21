from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Reclamation(models.Model):
    _name = 'reclamation'
    _description = 'Réclamation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    # Champs principaux
    name = fields.Char(string='Référence', required=True, copy=False, readonly=True,
                       default=lambda self: self.env['ir.sequence'].next_by_code('reclamation.sequence') or 'Nouveau')
    date_heure = fields.Datetime(string='Date et Heure', required=True, default=fields.Datetime.now)
    client_id = fields.Many2one('res.partner', string='Client')
    nom_central_id = fields.Many2one('pv.installation', string='Nom Instalation')
    adresse = fields.Char(related='nom_central_id.address_id', string='Adresse', readonly=True)
    description = fields.Text(string='Description', required=True)
    code_alarm_id = fields.Many2one('alarm.management', string='Code Alarm')
    priorite_urgence = fields.Selection([
        ('basse', 'Basse'),
        ('moyenne', 'Moyenne'),
        ('haute', 'Haute')
    ], string='Priorité d\'urgence')
    date_disponibilite = fields.Datetime(string='Date de disponibilité', required=True, default=fields.Datetime.now)
    cause_alarme = fields.Text(string='Cause de l\'Alarme')


    # Champ pour lier à fiche.intervention (si ce modèle existe ou sera créé)
    intervention_ids = fields.One2many('fiche.intervention', 'reclamation_id', string='Fiches d\'intervention')
    intervention_count = fields.Integer(compute='_compute_intervention_count', string='Nombre d\'interventions')

    def action_view_alarm_action_plan(self):
        """
        Affiche le plan d'action associé au code d'alarme de la réclamation
        """
        self.ensure_one()
        if not self.code_alarm_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Attention'),
                    'message': _('Aucun code d\'alarme associé à cette réclamation'),
                    'sticky': False,
                    'type': 'warning'
                }
            }

        # Si le code d'alarme n'a pas encore de plan d'action, le générer automatiquement
        if not self.code_alarm_id.action_plan_html:
            self.code_alarm_id.action_generate_action_plan()

        return {
            'name': _('Plan d\'action pour l\'alarme %s') % self.code_alarm_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'alarm.management',
            'view_mode': 'form',
            'res_id': self.code_alarm_id.id,
            'target': 'current',
        }

    @api.onchange('client_id')
    def _onchange_client_id(self):
        """When client changes, reset installation and update domain"""
        self.nom_central_id = False
        return {'domain': {'nom_central_id': [('client', '=', self.client_id.id)]}}

    def _compute_intervention_count(self):
        for rec in self:
            rec.intervention_count = self.env['fiche.intervention'].search_count([('reclamation_id', '=', rec.id)])

    def action_view_interventions(self):
        self.ensure_one()
        return {
            'name': 'Interventions',
            'view_mode': 'tree,form',
            'res_model': 'fiche.intervention',
            'domain': [('reclamation_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_reclamation_id': self.id}
        }



    @api.model
    def create(self, vals):
        if vals.get('name', 'Nouveau') == 'Nouveau':
            vals['name'] = self.env['ir.sequence'].next_by_code('reclamation.sequence') or 'Nouveau'
        return super(Reclamation, self).create(vals)

    def _send_notification_email(self):
        """Envoi d'email lors de la fermeture d'une réclamation"""
        self.ensure_one()
        if not self.contrat_id or not self.contrat_id.email:
            return False

        template = self.env.ref('pv_management.email_template_reclamation_closed', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)

    def action_create_intervention(self):
        """Bouton pour créer une fiche d'intervention"""
        self.ensure_one()
        fiche_intervention = self.env['fiche.intervention'].search([('reclamation_id','=',self.id)], limit=1)

        return {
            'name': 'Créer une fiche d\'intervention',
            'view_mode': 'form',
            'res_model': 'fiche.intervention',
            'type': 'ir.actions.act_window',
            'context': {
                'default_reclamation_id': self.id,
                'default_installation_id': self.nom_central_id.id,
                'default_adresse': self.adresse,
                'default_code_alarm_id': self.code_alarm_id.name,
            },
        }