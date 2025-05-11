from odoo import models, fields, api


class AgendaInterventionLine(models.Model):
    _name = 'agenda.intervention.line'
    _description = "Ligne d'agenda d'intervention"

    date_intervention = fields.Datetime(string='Date d\'intervention', required=True, default=fields.Datetime.now)
    description = fields.Text(string="Description de l'intervention", required=True)
    fiche_intervention_id = fields.Many2one('fiche.intervention', string="Fiche d'intervention")


class FicheIntervention(models.Model):
    _name = 'fiche.intervention'
    _description = 'Fiche d\'intervention'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    evaluation_ids = fields.One2many('pv.evaluation', 'intervention_id', string='Evaluations')
    evaluation_count = fields.Integer(compute='_compute_evaluation_count', string='Evaluation Count')

    name = fields.Char(string='Référence', required=True, copy=False, readonly=True,
                       default=lambda self: self.env['ir.sequence'].next_by_code(
                           'fiche.intervention.sequence') or 'Nouveau')
    # Type d'intervention (new field)
    type_intervention = fields.Selection([
        ('maintenance', 'Maintenance'),
        ('installation', 'Installation'),
        ('reparation', 'Réparation'),
        ('inspection', 'Inspection'),
        ('autre', 'Autre')
    ], string='Type d\'intervention', required=True, tracking=True)

    # Agenda (new field)
    agenda_line_ids = fields.One2many('agenda.intervention.line', 'fiche_intervention_id', string='Agenda', help="Programme prévu pour l'intervention")
    installation_id = fields.Many2one('pv.installation', string='Installation', readonly=True)
    adresse = fields.Char(string='Adresse', readonly=True)
    reclamation_id = fields.Many2one('reclamation', string='Réclamation associée', readonly=True)
    code_alarm_id = fields.Char(string='Code Alarm' , readonly=True)


    # Fiches de réponse liées
    reponse_ids = fields.One2many('fiche.reponse', 'intervention_id', string='Fiches de Réponse')
    reponse_count = fields.Integer(compute='_compute_reponse_count', string='Nombre de Réponses')

    # Updated state field to match Help Desk
    state = fields.Selection([
        ('draft', 'Ouvert'),
        ('in_progress', 'En cours'),
        ('closed', 'Fermé'),
    ], string='État', default='draft', tracking=True)

    # Field for technician - may need to be expanded to team
    technicien_id = fields.Many2one('hr.employee', string='Technicien')
    # Team field (new)
    equipe_intervention_ids = fields.Many2many('hr.employee', string='Équipe d\'Intervention')

    # Intervention text (conditional field)
    intervention_text = fields.Text(string='Bilan d\'intervention',
                                    help="Bilan final de l'intervention après fermeture")

    def _compute_evaluation_count(self):
        for rec in self:
            rec.evaluation_count = self.env['pv.evaluation'].search_count([('intervention_id', '=', rec.id)])

    def action_view_evaluations(self):
        self.ensure_one()
        return {
            'name': 'Evaluations',
            'view_mode': 'tree,form',
            'res_model': 'pv.evaluation',
            'domain': [('intervention_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_intervention_id': self.id, 'default_installation_id': self.installation_id.id}
        }

    def action_create_evaluation(self):
        """Create a new evaluation for this intervention"""
        self.ensure_one()
        return {
            'name': 'Create Evaluation',
            'view_mode': 'form',
            'res_model': 'pv.evaluation',
            'type': 'ir.actions.act_window',
            'context': {
                'default_intervention_id': self.id,
                'default_installation_id': self.installation_id.id,
            }
        }
    def _compute_reponse_count(self):
        for rec in self:
            rec.reponse_count = self.env['fiche.reponse'].search_count([('intervention_id', '=', rec.id)])

    def action_view_reponses(self):
        self.ensure_one()
        return {
            'name': 'Fiches de Réponse',
            'view_mode': 'tree,form',
            'res_model': 'fiche.reponse',
            'domain': [('intervention_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_intervention_id': self.id}
        }

    def action_create_reponse(self):
        """Bouton pour créer une fiche de réponse"""
        self.ensure_one()
        return {
            'name': 'Créer une fiche de réponse',
            'view_mode': 'form',
            'res_model': 'fiche.reponse',
            'type': 'ir.actions.act_window',
            'context': {
                'default_intervention_id': self.id,
                'default_date_cloture': fields.Date.today(),
            },
        }

    def action_view_reclamation(self):
        """Bouton pour revenir à la réclamation d'origine"""
        self.ensure_one()
        if not self.reclamation_id:
            return

        return {
            'name': 'Réclamation',
            'view_mode': 'form',
            'res_model': 'reclamation',
            'res_id': self.reclamation_id.id,
            'type': 'ir.actions.act_window',
        }

    # Add state change methods
    def action_draft(self):
        self.write({'state': 'draft'})

    def action_in_progress(self):
        self.write({'state': 'in_progress'})

    def action_closed(self):
        self.write({'state': 'closed'})