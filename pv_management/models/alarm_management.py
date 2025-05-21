from odoo import models, fields, api, _

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

    # Nouveaux champs pour le plan d'action IA
    action_plan_html = fields.Html(string='Plan d\'action IA', translate=True)
    last_action_plan_date = fields.Datetime(string='Dernière mise à jour du plan', readonly=True)
    action_plan_severity = fields.Selection([
        ('low', 'Faible'),
        ('medium', 'Moyen'),
        ('high', 'Élevé'),
        ('critical', 'Critique')
    ], string='Gravité', readonly=True)
    action_plan_resolution_time = fields.Float(string='Temps estimé (heures)', readonly=True)
    requires_specialist = fields.Boolean(string='Spécialiste requis', readonly=True)

    @api.onchange('partie')
    def _onchange_partie(self):
        # Clear the marque_onduleur_id when partie is not 'onduleur'
        if self.partie != 'onduleur':
            self.marque_onduleur_id = False

    def action_generate_action_plan(self):
        """
        Génère un plan d'action IA pour le code d'alarme
        """
        self.ensure_one()
        openai_service = self.env['pv.management.openai.service']

        # Rechercher des occurrences de ce code d'alarme dans les réclamations
        reclamations = self.env['reclamation'].search([('code_alarm_id', '=', self.id)], limit=10)

        # Préparer les données pour l'IA
        alarm_data = {
            'id': self.id,
            'name': self.name,
            'partie': self.partie,
            'code_alarm': self.code_alarm,
            'marque_onduleur': self.marque_onduleur_id.name if self.marque_onduleur_id else None,
        }

        # Ajouter l'historique des réclamations associées à ce code d'alarme
        if reclamations:
            alarm_data['reclamations'] = []
            for rec in reclamations:
                intervention = self.env['fiche.intervention'].search([('reclamation_id', '=', rec.id)], limit=1)
                alarm_data['reclamations'].append({
                    'date': str(rec.date_heure),
                    'description': rec.description,
                    'installation_type': rec.nom_central_id.type_installation if rec.nom_central_id else None,
                    'priority': rec.priorite_urgence,
                    'has_intervention': bool(intervention),
                    'intervention_state': intervention.state if intervention else None,
                    'intervention_text': intervention.intervention_text if intervention else None,
                })

        action_plan = openai_service.generate_alarm_action_plan(alarm_data)
        if action_plan:
            self.write({
                'action_plan_html': action_plan.get('html_content',
                                                    '<p>Erreur lors de la génération du plan d\'action.</p>'),
                'last_action_plan_date': fields.Datetime.now(),
                'action_plan_severity': action_plan.get('severity', 'medium'),
                'action_plan_resolution_time': action_plan.get('estimated_resolution_time', 0.0),
                'requires_specialist': action_plan.get('requires_specialist', False),
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Plan d\'action généré'),
                    'message': _('Le plan d\'action pour l\'alarme %s a été généré avec succès.') % self.name,
                    'sticky': False,
                    'type': 'success'
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Erreur'),
                    'message': _(
                        'Impossible de générer le plan d\'action. Vérifiez la configuration de l\'API OpenAI.'),
                    'sticky': False,
                    'type': 'warning'
                }
            }