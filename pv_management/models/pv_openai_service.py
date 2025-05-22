from odoo import models, fields, api, _
import json
import logging
from datetime import datetime, timedelta
import requests
from odoo.exceptions import UserError, ValidationError
import hashlib
import time

_logger = logging.getLogger(__name__)


class PVOpenAIService(models.AbstractModel):
    _name = 'pv.management.openai.service'
    _description = 'Service d\'intégration OpenAI pour la gestion des installations PV'

    @api.model
    def _get_api_key(self):
        """Récupérer la clé API de manière sécurisée"""
        try:
            api_key = self.env['ir.config_parameter'].sudo().get_param('pv_management.openai_api_key')
            if not api_key or api_key == 'YOUR_API_KEY_HERE':
                _logger.error("Clé API OpenAI non configurée ou invalide")
                return False
            return api_key
        except Exception as e:
            _logger.error(f"Erreur lors de la récupération de la clé API: {str(e)}")
            return False

    @api.model
    def _make_openai_request(self, messages, model="gpt-4o-mini", temperature=0.7, max_retries=3):
        """
        Requête OpenAI améliorée avec gestion d'erreurs et retry logic
        """
        api_key = self._get_api_key()
        if not api_key:
            return False

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Odoo-PV-Management/1.0"
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "max_tokens": 4000
        }

        for attempt in range(max_retries):
            try:
                _logger.info(f"Tentative {attempt + 1} de requête OpenAI")

                response = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60  # Timeout de 60 secondes
                )

                # Log du statut de la réponse
                _logger.info(f"Statut de la réponse OpenAI: {response.status_code}")

                if response.status_code == 429:  # Rate limit
                    wait_time = 2 ** attempt  # Exponential backoff
                    _logger.warning(f"Rate limit atteint, attente de {wait_time} secondes")
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()

                result = response.json()

                if 'choices' in result and len(result['choices']) > 0:
                    content = result['choices'][0]['message']['content']
                    _logger.info("Réponse OpenAI reçue avec succès")
                    return content
                else:
                    _logger.error(f"Format de réponse inattendu: {result}")
                    return False

            except requests.exceptions.Timeout:
                _logger.error(f"Timeout lors de la tentative {attempt + 1}")
                if attempt == max_retries - 1:
                    return False
                time.sleep(2 ** attempt)

            except requests.exceptions.RequestException as e:
                _logger.error(f"Erreur de requête lors de la tentative {attempt + 1}: {str(e)}")
                if response.status_code >= 500:  # Server error, retry
                    if attempt == max_retries - 1:
                        return False
                    time.sleep(2 ** attempt)
                else:
                    return False

            except Exception as e:
                _logger.error(f"Erreur inattendue lors de la tentative {attempt + 1}: {str(e)}")
                return False

        return False

    @api.model
    def _validate_and_clean_response(self, response_data, required_fields, default_values=None):
        """
        Valide et nettoie les données de réponse de l'IA
        """
        if not response_data:
            return False

        if default_values is None:
            default_values = {}

        # Validation des champs requis
        for field in required_fields:
            if field not in response_data:
                _logger.warning(f"Champ requis manquant: {field}")
                response_data[field] = default_values.get(field, '')

        return response_data

    @api.model
    def _get_installation_context(self, installation_id=None):
        """
        Récupère le contexte détaillé d'une installation pour améliorer les prédictions
        """
        context = {}

        if installation_id:
            installation = self.env['pv.installation'].browse(installation_id)
            if installation.exists():
                # Récupérer les données météorologiques fictives (à adapter selon vos besoins)
                context['weather_conditions'] = {
                    'region': installation.district_steg_id.name if installation.district_steg_id else 'Unknown',
                    'installation_age': (
                                                    datetime.now().date() - installation.date_mise_en_service).days / 365 if installation.date_mise_en_service else 0
                }

                # Récupérer l'historique des performances
                evaluations = installation.evaluation_ids.sorted('date_evaluation', reverse=True)[:5]
                if evaluations:
                    context['performance_history'] = [{
                        'date': str(eval.date_evaluation),
                        'performance_ratio': eval.performance_ratio,
                        'energy_produced': eval.energy_produced,
                        'system_efficiency': eval.system_efficiency,
                        'panel_condition': eval.panel_condition,
                        'inverter_condition': eval.inverter_condition
                    } for eval in evaluations]

                # Récupérer l'historique des pannes
                reclamations = self.env['reclamation'].search([
                    ('nom_central_id', '=', installation.id)
                ], order='date_heure desc', limit=10)

                context['failure_history'] = [{
                    'date': str(rec.date_heure),
                    'alarm_code': rec.code_alarm_id.code_alarm if rec.code_alarm_id else '',
                    'description': rec.description,
                    'priority': rec.priorite_urgence
                } for rec in reclamations]

        return context

    @api.model
    def generate_alarm_action_plan(self, alarm_data):
        """
        Génère un plan d'action amélioré basé sur le code d'alarme
        """
        try:
            # Améliorer les données d'alarme avec du contexte
            enhanced_data = self._enhance_alarm_data(alarm_data)

            # Vérifier si un plan similaire existe déjà en cache
            cached_plan = self._check_cached_plan(enhanced_data)
            if cached_plan:
                _logger.info("Plan d'action récupéré depuis le cache")
                return cached_plan

            system_prompt = self._get_enhanced_alarm_system_prompt()
            user_prompt = self._build_alarm_user_prompt(enhanced_data)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            content = self._make_openai_request(messages,
                                                temperature=0.3)  # Température plus basse pour plus de cohérence
            if not content:
                return self._get_fallback_plan(enhanced_data)

            try:
                action_plan = json.loads(content)
            except json.JSONDecodeError as e:
                _logger.error(f"Erreur de parsing JSON: {str(e)}")
                return self._get_fallback_plan(enhanced_data)

            # Validation et nettoyage
            required_fields = ['diagnostic', 'severity', 'action_steps']
            default_values = {
                'diagnostic': 'Diagnostic automatique non disponible',
                'severity': 'medium',
                'action_steps': [],
                'prevention_measures': [],
                'estimated_resolution_time': 2.0,
                'requires_specialist': False
            }

            action_plan = self._validate_and_clean_response(action_plan, required_fields, default_values)
            if not action_plan:
                return self._get_fallback_plan(enhanced_data)

            # Post-traitement des données
            action_plan = self._post_process_action_plan(action_plan)

            # Mise en cache
            self._cache_plan(enhanced_data, action_plan)

            # Formater en HTML
            action_plan['html_content'] = self._format_action_plan_html(action_plan)

            return action_plan

        except Exception as e:
            _logger.error(f"Erreur dans generate_alarm_action_plan: {str(e)}")
            return self._get_fallback_plan(alarm_data)

    def _enhance_alarm_data(self, alarm_data):
        """
        Améliore les données d'alarme avec du contexte supplémentaire
        """
        enhanced_data = alarm_data.copy()

        # Ajouter des statistiques sur les occurrences de cette alarme
        if 'code_alarm' in alarm_data:
            alarm_stats = self._get_alarm_statistics(alarm_data['code_alarm'])
            enhanced_data['alarm_statistics'] = alarm_stats

        # Ajouter des informations sur la saisonnalité
        enhanced_data['current_season'] = self._get_current_season()

        # Ajouter des informations sur les tendances récentes
        enhanced_data['recent_trends'] = self._get_recent_alarm_trends()

        return enhanced_data

    def _get_alarm_statistics(self, alarm_code):
        """
        Récupère les statistiques sur un code d'alarme spécifique
        """
        domain = [('code_alarm_id.code_alarm', '=', alarm_code)]
        reclamations = self.env['reclamation'].search(domain)

        if not reclamations:
            return {}

        total_count = len(reclamations)
        resolved_count = len([r for r in reclamations if self.env['fiche.intervention'].search(
            [('reclamation_id', '=', r.id), ('state', '=', 'closed')])])

        return {
            'total_occurrences': total_count,
            'resolution_rate': (resolved_count / total_count * 100) if total_count > 0 else 0,
            'average_priority': self._calculate_average_priority(reclamations),
            'common_installation_types': self._get_common_installation_types(reclamations)
        }

    def _calculate_average_priority(self, reclamations):
        """
        Calcule la priorité moyenne des réclamations
        """
        priority_values = {'basse': 1, 'moyenne': 2, 'haute': 3}
        total_score = sum(priority_values.get(r.priorite_urgence, 2) for r in reclamations)
        return total_score / len(reclamations) if reclamations else 2

    def _get_common_installation_types(self, reclamations):
        """
        Identifie les types d'installation les plus concernés par cette alarme
        """
        types = {}
        for rec in reclamations:
            if rec.nom_central_id and rec.nom_central_id.type_installation:
                inst_type = rec.nom_central_id.type_installation
                types[inst_type] = types.get(inst_type, 0) + 1
        return types

    def _get_current_season(self):
        """
        Détermine la saison actuelle (utile pour les problèmes saisonniers)
        """
        month = datetime.now().month
        if month in [12, 1, 2]:
            return 'hiver'
        elif month in [3, 4, 5]:
            return 'printemps'
        elif month in [6, 7, 8]:
            return 'été'
        else:
            return 'automne'

    def _get_recent_alarm_trends(self):
        """
        Analyse les tendances récentes des alarmes
        """
        last_30_days = datetime.now() - timedelta(days=30)
        recent_alarms = self.env['reclamation'].search([
            ('date_heure', '>=', last_30_days)
        ])

        alarm_counts = {}
        for rec in recent_alarms:
            if rec.code_alarm_id:
                code = rec.code_alarm_id.code_alarm
                alarm_counts[code] = alarm_counts.get(code, 0) + 1

        return sorted(alarm_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    def _get_enhanced_alarm_system_prompt(self):
        """
        Prompt système amélioré pour l'analyse d'alarmes
        """
        return """
        Tu es un expert senior en maintenance d'installations photovoltaïques avec 15+ années d'expérience.
        Tu as une connaissance approfondie des systèmes PV, des onduleurs, des modules, et des problèmes courants.

        Analyse les données d'alarme fournies en tenant compte de:
        1. L'historique des occurrences de cette alarme
        2. Les conditions saisonnières et météorologiques
        3. Le type d'installation et sa configuration
        4. Les tendances récentes observées
        5. Les meilleures pratiques de l'industrie

        Génère un plan d'action DÉTAILLÉ et PRATIQUE qui inclut:
        - Un diagnostic précis basé sur ton expertise
        - Des étapes de dépannage progressives (du plus simple au plus complexe)
        - Des considérations de sécurité spécifiques
        - Des outils et pièces de rechange nécessaires
        - Des mesures préventives adaptées au contexte

        Réponds UNIQUEMENT avec un objet JSON valide dans ce format exact:
        {
            "diagnostic": "Diagnostic détaillé du problème",
            "severity": "low|medium|high|critical",
            "estimated_resolution_time": float,
            "requires_specialist": boolean,
            "action_steps": [
                {
                    "step": int,
                    "title": "Titre court de l'étape",
                    "description": "Description détaillée",
                    "estimated_time": int,
                    "requires_tools": ["outil1", "outil2"],
                    "requires_parts": ["pièce1", "pièce2"],
                    "technical_level": "basic|intermediate|advanced",
                    "safety_precautions": ["précaution1", "précaution2"],
                    "success_criteria": "Comment savoir si l'étape a réussi"
                }
            ],
            "prevention_measures": ["mesure1", "mesure2"],
            "additional_notes": "Notes importantes",
            "documentation_references": ["référence1", "référence2"],
            "follow_up_actions": ["action1", "action2"]
        }
        """

    def _build_alarm_user_prompt(self, enhanced_data):
        """
        Construit un prompt utilisateur détaillé
        """
        base_prompt = f"""
        DONNÉES D'ALARME À ANALYSER:
        {json.dumps(enhanced_data, indent=2, ensure_ascii=False)}

        CONTEXTE SUPPLÉMENTAIRE:
        """

        if enhanced_data.get('alarm_statistics'):
            stats = enhanced_data['alarm_statistics']
            base_prompt += f"""
        - Cette alarme est survenue {stats.get('total_occurrences', 0)} fois au total
        - Taux de résolution: {stats.get('resolution_rate', 0):.1f}%
        - Priorité moyenne: {stats.get('average_priority', 2):.1f}/3
        """

        if enhanced_data.get('current_season'):
            base_prompt += f"""
        - Saison actuelle: {enhanced_data['current_season']}
        """

        if enhanced_data.get('recent_trends'):
            base_prompt += f"""
        - Tendances récentes: {enhanced_data['recent_trends'][:3]}
        """

        base_prompt += """

        INSTRUCTIONS:
        Analyse ces informations et génère un plan d'action optimal pour résoudre cette alarme.
        Prends en compte l'historique, les tendances, et le contexte spécifique.
        Sois PRÉCIS, PRATIQUE et SÉCURITAIRE dans tes recommandations.
        """

        return base_prompt

    def _check_cached_plan(self, alarm_data):
        """
        Vérifie si un plan similaire existe en cache (simplifié pour cette démo)
        """
        # Dans une implémentation réelle, vous pourriez utiliser Redis ou une table de cache
        return False

    def _cache_plan(self, alarm_data, action_plan):
        """
        Met en cache le plan d'action pour une réutilisation future
        """
        # Dans une implémentation réelle, vous stockeriez cela dans Redis ou une table de cache
        pass

    def _get_fallback_plan(self, alarm_data):
        """
        Plan d'action de secours en cas d'échec de l'IA
        """
        return {
            'diagnostic': f"Problème détecté avec le code d'alarme: {alarm_data.get('code_alarm', 'Inconnu')}",
            'severity': 'medium',
            'estimated_resolution_time': 4.0,
            'requires_specialist': True,
            'action_steps': [
                {
                    'step': 1,
                    'title': 'Vérification initiale',
                    'description': 'Vérifier l\'état général de l\'installation et consulter la documentation technique',
                    'estimated_time': 30,
                    'requires_tools': ['Multimètre', 'Documentation technique'],
                    'requires_parts': [],
                    'technical_level': 'basic',
                    'safety_precautions': ['Couper l\'alimentation', 'Porter des EPI'],
                    'success_criteria': 'État général évalué'
                },
                {
                    'step': 2,
                    'title': 'Contact support technique',
                    'description': 'Contacter le support technique du fabricant avec les détails de l\'alarme',
                    'estimated_time': 60,
                    'requires_tools': ['Téléphone', 'Documentation installation'],
                    'requires_parts': [],
                    'technical_level': 'basic',
                    'safety_precautions': [],
                    'success_criteria': 'Support technique contacté'
                }
            ],
            'prevention_measures': [
                'Maintenance préventive régulière',
                'Surveillance continue des performances',
                'Formation du personnel technique'
            ],
            'additional_notes': 'Plan d\'action générique. Consulter un expert pour un diagnostic approfondi.',
            'documentation_references': ['Manuel utilisateur', 'Guide de dépannage'],
            'follow_up_actions': ['Planifier maintenance préventive', 'Documenter la résolution']
        }

    def _post_process_action_plan(self, action_plan):
        """
        Post-traitement du plan d'action pour améliorer la qualité
        """
        # Validation de la cohérence temporelle
        if action_plan.get('estimated_resolution_time', 0) <= 0:
            total_step_time = sum(step.get('estimated_time', 30) for step in action_plan.get('action_steps', [])) / 60
            action_plan['estimated_resolution_time'] = max(total_step_time, 1.0)

        # Validation des étapes
        for i, step in enumerate(action_plan.get('action_steps', [])):
            if 'step' not in step:
                step['step'] = i + 1
            if 'title' not in step:
                step['title'] = f"Étape {i + 1}"
            if 'success_criteria' not in step:
                step['success_criteria'] = "Étape terminée avec succès"

        return action_plan

    def _format_action_plan_html(self, action_plan):
        """
        Formate le plan d'action en HTML amélioré
        """
        severity_colors = {
            'low': '#28a745',
            'medium': '#ffc107',
            'high': '#fd7e14',
            'critical': '#dc3545'
        }

        severity_color = severity_colors.get(action_plan.get('severity', 'medium'), '#ffc107')
        severity_text_color = '#333' if action_plan.get('severity') == 'medium' else 'white'

        html = f"""
        <div class="action-plan-container">
            <div class="action-plan-header">
                <h2>Plan d'Action Intelligent</h2>
                <div class="plan-metadata">
                    <span class="severity-badge" style="background-color: {severity_color}; color: {severity_text_color};">
                        {action_plan.get('severity', 'medium').capitalize()}
                    </span>
                    <span class="time-estimate">
                        ⏱️ {action_plan.get('estimated_resolution_time', 0):.1f}h estimées
                    </span>
                    <span class="specialist-required">
                        {'👨‍🔧 Spécialiste requis' if action_plan.get('requires_specialist', False) else '✅ Technicien standard'}
                    </span>
                </div>
            </div>

            <div class="diagnostic-section">
                <h3>🔍 Diagnostic</h3>
                <div class="diagnostic-content">
                    {action_plan.get('diagnostic', 'Diagnostic non disponible')}
                </div>
            </div>

            <div class="action-steps-section">
                <h3>📋 Plan d'Action Détaillé</h3>
                <div class="steps-container">
        """

        for step in action_plan.get('action_steps', []):
            level_colors = {
                'basic': '#e8f5e8',
                'intermediate': '#e8f2ff',
                'advanced': '#ffe8e8'
            }
            level_icons = {
                'basic': '🟢',
                'intermediate': '🟡',
                'advanced': '🔴'
            }

            level = step.get('technical_level', 'basic')
            level_color = level_colors.get(level, '#f8f9fa')
            level_icon = level_icons.get(level, '🟢')

            html += f"""
                    <div class="step-card" style="border-left: 4px solid {severity_color};">
                        <div class="step-header">
                            <span class="step-number">{step.get('step', '')}</span>
                            <h4>{step.get('title', step.get('description', '')[:50])}</h4>
                            <div class="step-badges">
                                <span class="level-badge" style="background-color: {level_color};">
                                    {level_icon} {level.capitalize()}
                                </span>
                                <span class="time-badge">⏰ {step.get('estimated_time', 0)} min</span>
                            </div>
                        </div>

                        <div class="step-content">
                            <p class="step-description">{step.get('description', '')}</p>

                            <div class="step-details">
            """

            if step.get('requires_tools'):
                html += f"""
                                <div class="detail-section">
                                    <strong>🔧 Outils nécessaires:</strong>
                                    <ul class="detail-list">
                """
                for tool in step.get('requires_tools', []):
                    html += f"<li>{tool}</li>"
                html += "</ul></div>"

            if step.get('requires_parts'):
                html += f"""
                                <div class="detail-section">
                                    <strong>🔩 Pièces nécessaires:</strong>
                                    <ul class="detail-list">
                """
                for part in step.get('requires_parts', []):
                    html += f"<li>{part}</li>"
                html += "</ul></div>"

            if step.get('safety_precautions'):
                html += f"""
                                <div class="detail-section safety-section">
                                    <strong>⚠️ Précautions de sécurité:</strong>
                                    <ul class="safety-list">
                """
                for precaution in step.get('safety_precautions', []):
                    html += f"<li>{precaution}</li>"
                html += "</ul></div>"

            if step.get('success_criteria'):
                html += f"""
                                <div class="detail-section success-section">
                                    <strong>✅ Critères de succès:</strong>
                                    <p>{step.get('success_criteria', '')}</p>
                                </div>
                """

            html += """
                            </div>
                        </div>
                    </div>
            """

        html += """
                </div>
            </div>
        """

        # Section prévention
        if action_plan.get('prevention_measures'):
            html += """
            <div class="prevention-section">
                <h3>🛡️ Mesures Préventives</h3>
                <ul class="prevention-list">
            """
            for measure in action_plan.get('prevention_measures', []):
                html += f"<li>{measure}</li>"
            html += "</ul></div>"

        # Section suivi
        if action_plan.get('follow_up_actions'):
            html += """
            <div class="followup-section">
                <h3>📈 Actions de Suivi</h3>
                <ul class="followup-list">
            """
            for action in action_plan.get('follow_up_actions', []):
                html += f"<li>{action}</li>"
            html += "</ul></div>"

        # Section notes
        if action_plan.get('additional_notes'):
            html += f"""
            <div class="notes-section">
                <h3>📝 Notes Importantes</h3>
                <div class="notes-content">
                    {action_plan.get('additional_notes', '')}
                </div>
            </div>
            """

        # Section références
        if action_plan.get('documentation_references'):
            html += """
            <div class="references-section">
                <h3>📚 Références Documentation</h3>
                <ul class="references-list">
            """
            for ref in action_plan.get('documentation_references', []):
                html += f"<li>{ref}</li>"
            html += "</ul></div>"

        # CSS amélioré
        html += """
        </div>

        <style>
            .action-plan-container {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                max-width: 100%;
                margin: 0 auto;
                background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                border-radius: 12px;
                padding: 24px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            }

            .action-plan-header {
                text-align: center;
                margin-bottom: 24px;
                padding-bottom: 16px;
                border-bottom: 2px solid #e9ecef;
            }

            .action-plan-header h2 {
                color: #2c3e50;
                margin-bottom: 12px;
                font-size: 24px;
                font-weight: 600;
            }

            .plan-metadata {
                display: flex;
                justify-content: center;
                gap: 16px;
                flex-wrap: wrap;
            }

            .severity-badge, .time-estimate, .specialist-required {
                padding: 6px 12px;
                border-radius: 20px;
                font-size: 14px;
                font-weight: 500;
                background: white;
                border: 1px solid #ddd;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }

            .diagnostic-section, .action-steps-section, .prevention-section, 
            .followup-section, .notes-section, .references-section {
                background: white;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 20px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
            }

            .diagnostic-section h3, .action-steps-section h3, .prevention-section h3,
            .followup-section h3, .notes-section h3, .references-section h3 {
                color: #2c3e50;
                margin-bottom: 12px;
                font-size: 18px;
                font-weight: 600;
                border-bottom: 1px solid #e9ecef;
                padding-bottom: 8px;
            }

            .diagnostic-content, .notes-content {
                background: #f8f9fa;
                padding: 16px;
                border-radius: 6px;
                border-left: 4px solid #007bff;
                line-height: 1.6;
            }

            .step-card {
                background: #fdfdfd;
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 16px;
                border: 1px solid #e9ecef;
                transition: transform 0.2s ease, box-shadow 0.2s ease;
            }

            .step-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 12px rgba(0, 0, 0, 0.1);
            }

            .step-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 12px;
                flex-wrap: wrap;
                gap: 8px;
            }

            .step-number {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                width: 32px;
                height: 32px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: bold;
                font-size: 14px;
            }

            .step-header h4 {
                flex: 1;
                margin: 0 12px;
                color: #2c3e50;
                font-size: 16px;
                font-weight: 600;
            }

            .step-badges {
                display: flex;
                gap: 8px;
                flex-wrap: wrap;
            }

            .level-badge, .time-badge {
                padding: 4px 8px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: 500;
                border: 1px solid #ddd;
            }

            .step-description {
                color: #495057;
                line-height: 1.6;
                margin-bottom: 16px;
                padding: 12px;
                background: #f8f9fa;
                border-radius: 6px;
                border-left: 3px solid #17a2b8;
            }

            .step-details {
                display: grid;
                gap: 12px;
            }

            .detail-section {
                padding: 12px;
                border-radius: 6px;
                background: #f8f9fa;
            }

            .safety-section {
                background: #fff3cd;
                border-left: 4px solid #ffc107;
            }

            .success-section {
                background: #d4edda;
                border-left: 4px solid #28a745;
            }

            .detail-list, .safety-list, .prevention-list, .followup-list, .references-list {
                margin: 8px 0 0 0;
                padding-left: 20px;
            }

            .detail-list li, .safety-list li, .prevention-list li, 
            .followup-list li, .references-list li {
                margin-bottom: 4px;
                line-height: 1.4;
            }

            .safety-list li::marker {
                content: "⚠️ ";
            }

            .prevention-list li::marker {
                content: "🛡️ ";
            }

            .followup-list li::marker {
                content: "📈 ";
            }

            .references-list li::marker {
                content: "📖 ";
            }

            @media (max-width: 768px) {
                .action-plan-container {
                    padding: 16px;
                }

                .plan-metadata {
                    flex-direction: column;
                    align-items: center;
                }

                .step-header {
                    flex-direction: column;
                    align-items: flex-start;
                }

                .step-badges {
                    align-self: flex-end;
                }
            }

            /* Animations */
            @keyframes slideIn {
                from {
                    opacity: 0;
                    transform: translateY(20px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }

            .step-card {
                animation: slideIn 0.3s ease-out;
            }

            .step-card:nth-child(n) {
                animation-delay: calc(n * 0.1s);
            }
        </style>
        """

        return html

    @api.model
    def predict_maintenance_needs(self, installation_data_json):
        """
        Prédiction de maintenance améliorée avec plus de contexte
        """
        try:
            installation_data = json.loads(installation_data_json) if isinstance(installation_data_json,
                                                                                 str) else installation_data_json

            # Enrichir les données avec du contexte
            enhanced_data = self._enrich_installation_data(installation_data)

            system_prompt = """
            Tu es un expert en maintenance prédictive pour les installations photovoltaïques.
            Analyse les données d'installation complètes pour prédire avec précision les besoins de maintenance.

            Prends en compte:
            - L'âge et l'historique de l'installation
            - Les conditions météorologiques et saisonnières
            - Les performances passées et tendances
            - L'historique des pannes et interventions
            - Les caractéristiques techniques des équipements

            Réponds en français avec un objet JSON structuré exactement comme ceci:
            {
                "maintenance_probability": float (0-100),
                "estimated_maintenance_date": "YYYY-MM-DD",
                "performance_impact": "low"|"medium"|"high"|"critical",
                "recommended_action": "routine_check"|"panel_cleaning"|"inverter_maintenance"|"full_inspection"|"urgent_repair",
                "priority_score": float (0-10),
                "confidence_level": float (0-100),
                "main_concerns": [
                    {
                        "component": "panels"|"inverters"|"wiring"|"monitoring"|"structure",
                        "issue": "description du problème potentiel",
                        "probability": float (0-100),
                        "impact": "low"|"medium"|"high"|"critical"
                    }
                ],
                "recommendations": string,
                "action_steps": [
                    {
                        "name": string,
                        "description": string,
                        "priority": "low"|"medium"|"high",
                        "estimated_cost": float,
                        "timeframe": "immediate"|"week"|"month"|"quarter"
                    }
                ],
                "performance_optimization": {
                    "current_efficiency": float,
                    "potential_improvement": float,
                    "optimization_actions": [string]
                }
            }
            """

            user_prompt = f"""
            DONNÉES D'INSTALLATION À ANALYSER:
            {json.dumps(enhanced_data, indent=2, ensure_ascii=False)}

            Effectue une analyse prédictive complète en tenant compte de tous les facteurs disponibles.
            Sois précis dans tes estimations et justifie tes recommandations.

            Réponds uniquement avec l'objet JSON demandé.
            """

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            content = self._make_openai_request(messages, temperature=0.2)
            if not content:
                return self._get_fallback_maintenance_prediction(enhanced_data)

            try:
                prediction_data = json.loads(content)
            except json.JSONDecodeError:
                return self._get_fallback_maintenance_prediction(enhanced_data)

            # Validation et post-traitement
            prediction_data = self._validate_maintenance_prediction(prediction_data)

            return prediction_data

        except Exception as e:
            _logger.error(f"Erreur dans predict_maintenance_needs: {str(e)}")
            return self._get_fallback_maintenance_prediction(installation_data)

    def _enrich_installation_data(self, installation_data):
        """
        Enrichit les données d'installation avec du contexte supplémentaire
        """
        enhanced_data = installation_data.copy()

        # Ajouter des métriques calculées
        if 'evaluations' in installation_data and installation_data['evaluations']:
            enhanced_data['performance_metrics'] = self._calculate_performance_metrics(installation_data['evaluations'])

        # Ajouter l'analyse des tendances
        if 'reclamations' in installation_data:
            enhanced_data['failure_analysis'] = self._analyze_failure_patterns(installation_data['reclamations'])

        # Ajouter le contexte environnemental
        enhanced_data['environmental_factors'] = {
            'current_season': self._get_current_season(),
            'installation_age_months': self._calculate_installation_age(installation_data.get('date_mise_en_service')),
            'climate_zone': self._get_climate_zone(installation_data.get('address', ''))
        }

        return enhanced_data

    def _calculate_performance_metrics(self, evaluations):
        """
        Calcule des métriques de performance avancées
        """
        if not evaluations:
            return {}

        performance_ratios = [eval.get('performance_ratio', 0) for eval in evaluations if eval.get('performance_ratio')]
        efficiencies = [eval.get('system_efficiency', 0) for eval in evaluations if eval.get('system_efficiency')]

        return {
            'avg_performance_ratio': sum(performance_ratios) / len(performance_ratios) if performance_ratios else 0,
            'avg_efficiency': sum(efficiencies) / len(efficiencies) if efficiencies else 0,
            'performance_trend': self._calculate_trend(performance_ratios),
            'efficiency_trend': self._calculate_trend(efficiencies),
            'degradation_rate': self._calculate_degradation_rate(performance_ratios)
        }

    def _calculate_trend(self, values):
        """
        Calcule la tendance des valeurs (positive, negative, stable)
        """
        if len(values) < 2:
            return 'insufficient_data'

        # Simple linear regression slope
        n = len(values)
        x_avg = (n - 1) / 2
        y_avg = sum(values) / n

        numerator = sum((i - x_avg) * (values[i] - y_avg) for i in range(n))
        denominator = sum((i - x_avg) ** 2 for i in range(n))

        if denominator == 0:
            return 'stable'

        slope = numerator / denominator

        if slope > 0.5:
            return 'improving'
        elif slope < -0.5:
            return 'declining'
        else:
            return 'stable'

    def _calculate_degradation_rate(self, performance_ratios):
        """
        Calcule le taux de dégradation annuel
        """
        if len(performance_ratios) < 2:
            return 0

        # Estimation simple basée sur la différence entre première et dernière valeur
        first_value = performance_ratios[0]
        last_value = performance_ratios[-1]

        if first_value <= 0:
            return 0

        # Calculer le pourcentage de dégradation
        degradation = ((first_value - last_value) / first_value) * 100
        return max(0, degradation)  # Éviter les valeurs négatives

    def _analyze_failure_patterns(self, reclamations):
        """
        Analyse les patterns de pannes
        """
        if not reclamations:
            return {}

        failure_frequency = len(reclamations)

        # Analyser les types d'alarmes
        alarm_types = {}
        for rec in reclamations:
            alarm = rec.get('code_alarm', 'unknown')
            alarm_types[alarm] = alarm_types.get(alarm, 0) + 1

        # Analyser la fréquence des pannes
        return {
            'total_failures': failure_frequency,
            'most_common_alarms': sorted(alarm_types.items(), key=lambda x: x[1], reverse=True)[:3],
            'failure_rate': self._calculate_failure_rate(reclamations),
            'severity_distribution': self._analyze_severity_distribution(reclamations)
        }

    def _calculate_failure_rate(self, reclamations):
        """
        Calcule le taux de panne (pannes par mois)
        """
        if not reclamations:
            return 0

        # Prendre les 12 derniers mois
        now = datetime.now()
        twelve_months_ago = now - timedelta(days=365)

        recent_failures = [
            rec for rec in reclamations
            if rec.get('date') and datetime.fromisoformat(rec['date'].replace('Z', '+00:00')).replace(
                tzinfo=None) > twelve_months_ago
        ]

        return len(recent_failures) / 12  # Pannes par mois

    def _analyze_severity_distribution(self, reclamations):
        """
        Analyse la distribution des priorités/gravités
        """
        priorities = [rec.get('priority', 'moyenne') for rec in reclamations]
        priority_count = {}
        for priority in priorities:
            priority_count[priority] = priority_count.get(priority, 0) + 1

        total = len(priorities)
        return {priority: (count / total * 100) for priority, count in priority_count.items()} if total > 0 else {}

    def _calculate_installation_age(self, date_mise_en_service):
        """
        Calcule l'âge de l'installation en mois
        """
        if not date_mise_en_service:
            return 0

        try:
            installation_date = datetime.fromisoformat(str(date_mise_en_service))
            age_delta = datetime.now() - installation_date
            return age_delta.days / 30.44  # Mois moyens
        except:
            return 0

    def _get_climate_zone(self, address):
        """
        Détermine la zone climatique (simplifié pour la Tunisie)
        """
        # Logique simplifiée - dans un vrai système, vous utiliseriez une API géo
        if any(region in str(address).lower() for region in ['tunis', 'ariana', 'ben arous']):
            return 'mediterranean_coastal'
        elif any(region in str(address).lower() for region in ['sfax', 'sousse', 'monastir']):
            return 'mediterranean_central'
        elif any(region in str(address).lower() for region in ['tozeur', 'gafsa', 'kebili']):
            return 'saharan'
        else:
            return 'continental'

    def _validate_maintenance_prediction(self, prediction_data):
        """
        Valide et corrige les données de prédiction de maintenance
        """
        # Validation des probabilités
        if 'maintenance_probability' in prediction_data:
            prob = prediction_data['maintenance_probability']
            prediction_data['maintenance_probability'] = max(0, min(100, float(prob)))

        # Validation des niveaux de confiance
        if 'confidence_level' in prediction_data:
            conf = prediction_data['confidence_level']
            prediction_data['confidence_level'] = max(0, min(100, float(conf)))

        # Validation des scores de priorité
        if 'priority_score' in prediction_data:
            score = prediction_data['priority_score']
            prediction_data['priority_score'] = max(0, min(10, float(score)))

        # Validation des dates
        if 'estimated_maintenance_date' not in prediction_data or not prediction_data['estimated_maintenance_date']:
            days_ahead = 30  # Par défaut, 30 jours
            if prediction_data.get('performance_impact') == 'critical':
                days_ahead = 3
            elif prediction_data.get('performance_impact') == 'high':
                days_ahead = 14
            elif prediction_data.get('performance_impact') == 'medium':
                days_ahead = 45
            else:
                days_ahead = 90

            prediction_data['estimated_maintenance_date'] = (datetime.now() + timedelta(days=days_ahead)).strftime(
                '%Y-%m-%d')

        # Formatage HTML des recommandations
        if 'recommendations' in prediction_data and not prediction_data['recommendations'].startswith('<'):
            recommendations = prediction_data['recommendations']
            prediction_data['recommendations'] = f"<p>{recommendations}</p>"

        return prediction_data

    def _get_fallback_maintenance_prediction(self, installation_data):
        """
        Prédiction de maintenance de secours
        """
        return {
            'maintenance_probability': 25.0,
            'estimated_maintenance_date': (datetime.now() + timedelta(days=60)).strftime('%Y-%m-%d'),
            'performance_impact': 'medium',
            'recommended_action': 'routine_check',
            'priority_score': 5.0,
            'confidence_level': 50.0,
            'main_concerns': [
                {
                    'component': 'panels',
                    'issue': 'Vérification générale recommandée',
                    'probability': 30.0,
                    'impact': 'low'
                }
            ],
            'recommendations': '<p>Maintenance préventive recommandée. Consultez un technicien qualifié.</p>',
            'action_steps': [
                {
                    'name': 'Inspection visuelle',
                    'description': 'Vérification générale de l\'état de l\'installation',
                    'priority': 'medium',
                    'estimated_cost': 200.0,
                    'timeframe': 'month'
                }
            ],
            'performance_optimization': {
                'current_efficiency': 85.0,
                'potential_improvement': 5.0,
                'optimization_actions': ['Nettoyage des panneaux', 'Vérification des connexions']
            }
        }