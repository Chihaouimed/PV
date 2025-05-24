from odoo import models, fields, api, _


class AlarmManagement(models.Model):
    _name = 'alarm.management'
    _description = 'Alarm Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    confidence_level = fields.Float(string='Niveau de confiance (%)', readonly=True)
    priority_score = fields.Float(string='Score de priorité (0-10)', readonly=True)
    environmental_factors = fields.Text(string='Facteurs environnementaux', readonly=True)
    name = fields.Char(string='Name', translate=True)
    partie = fields.Selection([
        ('onduleur', 'Onduleur'),
        ('module', 'Module'),
        ('installation', 'Installation'),
        ('batterie', 'Batterie'),
        ('autre', 'Autre')
    ], string='Partie', translate=True)
    marque_onduleur_id = fields.Many2one('marque.onduleur', string='Marque Onduleur')
    code_alarm = fields.Char(string='Code Alarm', translate=True)

    # Enhanced description field
    description = fields.Text(string='Description', translate=True, help="Description détaillée de l'alarme")

    # New enhancement fields
    severity = fields.Selection([
        ('info', 'Information'),
        ('warning', 'Avertissement'),
        ('error', 'Erreur'),
        ('critical', 'Critique')
    ], string='Sévérité', help="Niveau de gravité de l'alarme", default='warning')

    category = fields.Selection([
        ('electrical', 'Électrique'),
        ('mechanical', 'Mécanique'),
        ('communication', 'Communication'),
        ('performance', 'Performance'),
        ('safety', 'Sécurité')
    ], string='Catégorie', help="Catégorie du problème")

    # Occurrence tracking
    occurrence_count = fields.Integer(
        string='Occurrences',
        compute='_compute_occurrence_count',
        help="Nombre de fois que cette alarme est apparue"
    )

    last_occurrence_date = fields.Datetime(
        string='Dernière occurrence',
        compute='_compute_last_occurrence',
        help="Date de la dernière réclamation pour cette alarme"
    )

    # Resolution statistics
    avg_resolution_time = fields.Float(
        string='Temps moyen de résolution (h)',
        compute='_compute_resolution_stats',
        help="Temps moyen de résolution en heures"
    )

    resolution_rate = fields.Float(
        string='Taux de résolution (%)',
        compute='_compute_resolution_stats',
        help="Pourcentage d'interventions résolues"
    )

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

    @api.depends('code_alarm')
    def _compute_occurrence_count(self):
        for record in self:
            try:
                count = self.env['reclamation'].search_count([
                    ('code_alarm_id', '=', record.id)
                ])
                record.occurrence_count = count
            except:
                record.occurrence_count = 0

    @api.depends('code_alarm')
    def _compute_last_occurrence(self):
        for record in self:
            try:
                last_reclamation = self.env['reclamation'].search([
                    ('code_alarm_id', '=', record.id)
                ], order='date_heure desc', limit=1)
                record.last_occurrence_date = last_reclamation.date_heure if last_reclamation else False
            except:
                record.last_occurrence_date = False

    @api.depends('code_alarm')
    def _compute_resolution_stats(self):
        for record in self:
            try:
                reclamations = self.env['reclamation'].search([
                    ('code_alarm_id', '=', record.id)
                ])

                if not reclamations:
                    record.avg_resolution_time = 0.0
                    record.resolution_rate = 0.0
                    continue

                total_time = 0.0
                resolved_count = 0
                total_interventions = 0

                for reclamation in reclamations:
                    interventions = self.env['fiche.intervention'].search([
                        ('reclamation_id', '=', reclamation.id)
                    ])

                    for intervention in interventions:
                        total_interventions += 1
                        if intervention.state == 'closed':
                            resolved_count += 1
                            # Calculate resolution time
                            if intervention.create_date and reclamation.date_heure:
                                time_diff = intervention.create_date - reclamation.date_heure
                                total_time += time_diff.total_seconds() / 3600  # Convert to hours

                record.avg_resolution_time = total_time / resolved_count if resolved_count > 0 else 0.0
                record.resolution_rate = (
                            resolved_count / total_interventions * 100) if total_interventions > 0 else 0.0
            except:
                record.avg_resolution_time = 0.0
                record.resolution_rate = 0.0

    @api.onchange('code_alarm', 'partie')
    def _onchange_auto_description(self):
        """Auto-generate description suggestions based on alarm code and part"""
        if self.code_alarm and self.partie and not self.description:
            suggestions = {
                'onduleur': {
                    'default': 'Problème détecté au niveau de l\'onduleur. Vérifier les connexions et l\'état général.',
                    'patterns': {
                        'OVP': 'Surtension détectée - Tension d\'entrée dépassant les limites normales',
                        'UVP': 'Sous-tension détectée - Tension d\'entrée insuffisante',
                        'OCP': 'Surintensité détectée - Courant dépassant les limites de sécurité',
                        'OTP': 'Surchauffe détectée - Température interne excessive',
                        'COMM': 'Problème de communication - Perte de signal avec le système de monitoring'
                    }
                },
                'module': {
                    'default': 'Dysfonctionnement au niveau du module PV. Inspection visuelle recommandée.',
                    'patterns': {
                        'PERF': 'Baisse de performance - Production inférieure aux attentes',
                        'HOT': 'Point chaud détecté - Possible défaillance de cellule',
                        'SHADE': 'Ombrage détecté - Obstruction partielle du module',
                        'DIRT': 'Encrassement - Nettoyage nécessaire'
                    }
                },
                'installation': {
                    'default': 'Problème général de l\'installation. Diagnostic complet requis.',
                    'patterns': {
                        'GRID': 'Problème réseau - Connexion au réseau électrique',
                        'METER': 'Problème compteur - Dysfonctionnement du système de mesure',
                        'STRUCT': 'Problème structure - Vérification de la fixation'
                    }
                }
            }

            part_suggestions = suggestions.get(self.partie, {})

            # Check for pattern matches in alarm code
            for pattern, desc in part_suggestions.get('patterns', {}).items():
                if pattern.upper() in self.code_alarm.upper():
                    self.description = desc
                    return

            # Use default description for the part
            self.description = part_suggestions.get('default', '')

    @api.onchange('description', 'code_alarm')
    def _onchange_auto_severity(self):
        """Auto-determine severity based on description keywords"""
        if self.description:
            description_lower = self.description.lower()

            critical_keywords = ['surchauffe', 'surintensité', 'surtension', 'danger', 'urgent', 'critique']
            error_keywords = ['défaillance', 'panne', 'dysfonctionnement', 'erreur', 'problème']
            warning_keywords = ['baisse', 'diminution', 'encrassement', 'ombrage']

            if any(keyword in description_lower for keyword in critical_keywords):
                self.severity = 'critical'
            elif any(keyword in description_lower for keyword in error_keywords):
                self.severity = 'error'
            elif any(keyword in description_lower for keyword in warning_keywords):
                self.severity = 'warning'
            else:
                self.severity = 'info'

    @api.onchange('description')
    def _onchange_auto_category(self):
        """Auto-determine category based on description"""
        if self.description:
            description_lower = self.description.lower()

            if any(word in description_lower for word in ['tension', 'courant', 'électrique', 'réseau', 'compteur']):
                self.category = 'electrical'
            elif any(word in description_lower for word in ['communication', 'signal', 'connexion', 'monitoring']):
                self.category = 'communication'
            elif any(word in description_lower for word in ['performance', 'production', 'rendement', 'efficacité']):
                self.category = 'performance'
            elif any(word in description_lower for word in ['sécurité', 'danger', 'protection', 'urgent']):
                self.category = 'safety'
            elif any(word in description_lower for word in ['structure', 'fixation', 'mécanique', 'assemblage']):
                self.category = 'mechanical'

    def action_debug_openai(self):
        """Méthode de debug pour tester OpenAI"""
        try:
            openai_service = self.env['pv.management.openai.service']
            result = openai_service.debug_full_process()
        except Exception as e:
            result = f"Erreur: {str(e)}"

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Test OpenAI Debug'),
                'message': result,
                'sticky': True,
                'type': 'info'
            }
        }

    @api.onchange('partie')
    def _onchange_partie(self):
        # Clear the marque_onduleur_id when partie is not 'onduleur'
        if self.partie != 'onduleur':
            self.marque_onduleur_id = False

    def action_generate_action_plan(self):
        """
        Génère un plan d'action IA pour le code d'alarme avec feedback utilisateur amélioré
        """
        self.ensure_one()
        try:
            # Vérification des prérequis
            if not self.code_alarm:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Erreur'),
                        'message': _('Veuillez saisir un code d\'alarme avant de générer le plan d\'action.'),
                        'sticky': False,
                        'type': 'warning'
                    }
                }

            if not self.name:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Erreur'),
                        'message': _('Veuillez saisir un nom pour l\'alarme avant de générer le plan d\'action.'),
                        'sticky': False,
                        'type': 'warning'
                    }
                }

            openai_service = self.env['pv.management.openai.service']

            # Rechercher des occurrences de ce code d'alarme dans les réclamations
            reclamations = self.env['reclamation'].search([('code_alarm_id', '=', self.id)], limit=10)

            # Préparer les données pour l'IA
            alarm_data = {
                'id': self.id,
                'name': self.name,
                'partie': self.partie,
                'code_alarm': self.code_alarm,
                'description': self.description,
                'severity': self.severity,
                'category': self.category,
                'occurrence_count': self.occurrence_count,
                'avg_resolution_time': self.avg_resolution_time,
                'resolution_rate': self.resolution_rate,
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

            # Génération du plan d'action
            action_plan = openai_service.generate_alarm_action_plan(alarm_data)

            if action_plan:
                # Mise à jour des champs
                self.write({
                    'action_plan_html': action_plan.get('html_content',
                                                        '<p>Erreur lors de la génération du plan d\'action.</p>'),
                    'last_action_plan_date': fields.Datetime.now(),
                    'action_plan_severity': action_plan.get('severity', 'medium'),
                    'action_plan_resolution_time': action_plan.get('estimated_resolution_time', 0.0),
                    'requires_specialist': action_plan.get('requires_specialist', False),
                })

                # Committer la transaction pour s'assurer que les données sont sauvegardées
                self.env.cr.commit()

                # Retourner une action qui recharge la vue avec le nouvel onglet visible
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Plan d\'Action Généré'),
                    'res_model': 'alarm.management',
                    'res_id': self.id,
                    'view_mode': 'form',
                    'view_type': 'form',
                    'target': 'current',
                    'context': {
                        'default_active_tab': 'plan_action',  # Ouvrir directement l'onglet du plan d'action
                        'form_view_initial_mode': 'edit',
                    },
                    'flags': {'mode': 'edit'},
                }

            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Erreur'),
                        'message': _(
                            'Impossible de générer le plan d\'action. Vérifiez la configuration de l\'API OpenAI et votre connexion internet.'),
                        'sticky': False,
                        'type': 'warning'
                    }
                }

        except Exception as e:
            # Log de l'erreur pour le débogage
            import logging
            _logger = logging.getLogger(__name__)
            _logger.error(f"Erreur lors de la génération du plan d'action: {str(e)}")

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Erreur Technique'),
                    'message': f'Une erreur technique s\'est produite: {str(e)}. Consultez les logs pour plus de détails.',
                    'sticky': True,
                    'type': 'danger'
                }
            }