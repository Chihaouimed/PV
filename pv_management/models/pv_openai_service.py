from odoo import models, fields, api, _
import json
import logging
from datetime import datetime, timedelta
import requests
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class PVOpenAIService(models.AbstractModel):
    _name = 'pv.management.openai.service'
    _description = 'Service d\'intégration OpenAI pour la gestion des installations PV'

    @api.model
    def _get_api_key(self):
        """Récupérer la clé API OpenAI"""
        try:
            api_key = self.env['ir.config_parameter'].sudo().get_param('pv_management.openai_api_key')
            if not api_key or api_key in ['YOUR_API_KEY_HERE', 'YOUR_REAL_API_KEY_HERE']:
                _logger.warning("Clé API OpenAI non configurée")
                return False
            return api_key
        except Exception as e:
            _logger.error(f"Erreur lors de la récupération de la clé API: {str(e)}")
            return False

    @api.model
    def _test_api_key(self):
        """Teste si la clé API est valide"""
        api_key = self._get_api_key()
        if not api_key:
            return False, "Clé API non trouvée"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # Test simple avec l'endpoint models
        try:
            response = requests.get(
                "https://api.openai.com/v1/models",
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                return True, "Clé API valide"
            elif response.status_code == 401:
                return False, "Clé API invalide"
            else:
                return False, f"Erreur {response.status_code}: {response.text}"

        except Exception as e:
            return False, f"Erreur de connexion: {str(e)}"

    @api.model
    def _make_openai_request(self, messages, model="gpt-4o-mini", temperature=0.7):
        """Faire une requête à l'API OpenAI"""
        api_key = self._get_api_key()
        if not api_key:
            return False

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "max_tokens": 3000
        }

        try:
            _logger.info("Envoi de la requête à OpenAI...")

            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )

            _logger.info(f"Status Code: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                if 'choices' in result and len(result['choices']) > 0:
                    content = result['choices'][0]['message']['content']
                    _logger.info("Réponse OpenAI reçue avec succès")
                    return content
                else:
                    _logger.error(f"Format de réponse inattendu: {result}")
                    return False
            else:
                error_text = response.text
                _logger.error(f"Erreur API OpenAI {response.status_code}: {error_text}")
                return False

        except Exception as e:
            _logger.error(f"Erreur lors de la requête OpenAI: {str(e)}")
            return False

    @api.model
    def generate_alarm_action_plan(self, alarm_data):
        """Génère un plan d'action pour un code d'alarme avec données enrichies"""
        try:
            _logger.info(f"Génération du plan d'action pour: {alarm_data.get('name', 'Inconnu')}")

            # Prompt système enrichi
            system_prompt = """
            Tu es un expert en maintenance d'installations photovoltaïques avec une expertise approfondie.
            Analyse le code d'alarme, sa description, sa sévérité, et son historique pour générer un plan d'action détaillé et adapté.

            Prends en compte:
            - La description détaillée de l'alarme
            - Le niveau de sévérité (info, warning, error, critical)
            - La catégorie du problème (électrique, mécanique, communication, performance, sécurité)
            - L'historique des occurrences et le taux de résolution
            - Le temps moyen de résolution passé

            Réponds UNIQUEMENT avec un objet JSON valide dans ce format:
            {
                "diagnostic": "Description détaillée du problème basée sur toutes les informations",
                "severity": "low"|"medium"|"high"|"critical",
                "estimated_resolution_time": 2.0,
                "requires_specialist": true|false,
                "confidence_score": 85,
                "risk_assessment": "Évaluation des risques associés",
                "action_steps": [
                    {
                        "step": 1,
                        "title": "Titre de l'étape",
                        "description": "Description détaillée",
                        "estimated_time": 30,
                        "requires_tools": ["Multimètre", "Tournevis"],
                        "requires_parts": ["Fusible 10A"],
                        "technical_level": "basic"|"intermediate"|"advanced",
                        "safety_precautions": ["Couper l'alimentation", "Porter des EPI"],
                        "success_criteria": "Comment valider la réussite",
                        "failure_indicators": ["Signaux d'échec à surveiller"],
                        "cost_estimate": 50.0
                    }
                ],
                "prevention_measures": ["Mesures préventives spécifiques"],
                "monitoring_points": ["Points de surveillance post-intervention"],
                "escalation_criteria": ["Quand escalader vers un spécialiste"],
                "additional_notes": "Notes importantes contextuelles",
                "documentation_references": ["Références techniques pertinentes"],
                "follow_up_actions": ["Actions de suivi recommandées"],
                "warranty_considerations": "Considérations de garantie",
                "environmental_factors": ["Facteurs environnementaux à considérer"]
            }
            """

            # Construction du prompt utilisateur enrichi
            description_text = alarm_data.get('description', 'Aucune description fournie')
            severity = alarm_data.get('severity', 'unknown')
            category = alarm_data.get('category', 'unknown')
            occurrence_count = alarm_data.get('occurrence_count', 0)
            avg_resolution_time = alarm_data.get('avg_resolution_time', 0)
            resolution_rate = alarm_data.get('resolution_rate', 0)

            user_prompt = f"""
            ANALYSE D'ALARME PV:

            === INFORMATIONS DE BASE ===
            - Nom: {alarm_data.get('name', 'Inconnu')}
            - Code: {alarm_data.get('code_alarm', 'Inconnu')}
            - Description: {description_text}
            - Partie concernée: {alarm_data.get('partie', 'Inconnu')}
            - Marque onduleur: {alarm_data.get('marque_onduleur', 'Non spécifiée')}

            === CLASSIFICATION ===
            - Sévérité: {severity}
            - Catégorie: {category}

            === HISTORIQUE ET STATISTIQUES ===
            - Nombre d'occurrences: {occurrence_count}
            - Temps moyen de résolution: {avg_resolution_time:.1f} heures
            - Taux de résolution: {resolution_rate:.1f}%

            === HISTORIQUE DES RÉCLAMATIONS ===
            {len(alarm_data.get('reclamations', []))} réclamations enregistrées
            """

            # Ajouter les détails des réclamations si disponibles
            if alarm_data.get('reclamations'):
                user_prompt += "\n\nDétails des réclamations récentes:\n"
                for i, rec in enumerate(alarm_data.get('reclamations', [])[:5], 1):
                    user_prompt += f"""
            {i}. Date: {rec.get('date', 'N/A')}
               Type installation: {rec.get('installation_type', 'N/A')}
               Priorité: {rec.get('priority', 'N/A')}
               État intervention: {rec.get('intervention_state', 'N/A')}
                    """

            user_prompt += """

            MISSION: Génère un plan d'action détaillé, adapté à cette alarme spécifique, 
            en tenant compte de son historique et de sa criticité. Le plan doit être 
            pratique, sécurisé et optimisé pour maximiser les chances de résolution.
            """

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            content = self._make_openai_request(messages)
            if not content:
                return self._get_fallback_plan(alarm_data)

            try:
                action_plan = json.loads(content)
                _logger.info("Plan d'action généré avec succès")
            except json.JSONDecodeError as e:
                _logger.error(f"Erreur de parsing JSON: {str(e)}")
                return self._get_fallback_plan(alarm_data)

            # Validation et enrichissement
            action_plan = self._validate_and_enrich_action_plan(action_plan, alarm_data)

            # Génération du HTML enrichi
            action_plan['html_content'] = self._format_enhanced_action_plan_html(action_plan, alarm_data)

            return action_plan

        except Exception as e:
            _logger.error(f"Erreur dans generate_alarm_action_plan: {str(e)}")
            return self._get_fallback_plan(alarm_data)

    def _validate_and_enrich_action_plan(self, action_plan, alarm_data):
        """Valide et enrichit le plan d'action avec des données contextuelles"""
        # Valeurs par défaut enrichies
        defaults = {
            'diagnostic': 'Diagnostic automatique généré avec IA',
            'severity': 'medium',
            'estimated_resolution_time': 2.0,
            'requires_specialist': False,
            'confidence_score': 70,
            'risk_assessment': 'Risque modéré nécessitant attention standard',
            'action_steps': [],
            'prevention_measures': ['Maintenance préventive régulière', 'Surveillance continue'],
            'monitoring_points': ['Vérification post-intervention', 'Suivi performance'],
            'escalation_criteria': ['Échec de résolution après 2 tentatives'],
            'additional_notes': 'Plan généré automatiquement par IA',
            'documentation_references': ['Manuel utilisateur', 'Procédures techniques'],
            'follow_up_actions': ['Documenter la résolution', 'Planifier maintenance'],
            'warranty_considerations': 'Vérifier conditions de garantie avant intervention',
            'environmental_factors': ['Conditions météorologiques', 'Température ambiante']
        }

        # Appliquer les défauts si nécessaire
        for key, default_value in defaults.items():
            if key not in action_plan or not action_plan[key]:
                action_plan[key] = default_value

        # Ajustement de la sévérité basé sur l'historique
        occurrence_count = alarm_data.get('occurrence_count', 0)
        resolution_rate = alarm_data.get('resolution_rate', 100)

        if occurrence_count > 5 and resolution_rate < 50:
            if action_plan['severity'] in ['low', 'medium']:
                action_plan['severity'] = 'high'
            action_plan['requires_specialist'] = True
            action_plan['escalation_criteria'].append('Alarme récurrente avec faible taux de résolution')

        # Validation et enrichissement des étapes
        if not action_plan['action_steps']:
            action_plan['action_steps'] = self._generate_default_steps(alarm_data)

        return action_plan

    def _generate_default_steps(self, alarm_data):
        """Génère des étapes par défaut basées sur la partie et catégorie"""
        partie = alarm_data.get('partie', 'unknown')

        steps = [
            {
                'step': 1,
                'title': 'Évaluation sécuritaire initiale',
                'description': 'Vérifier la sécurité du site et couper l\'alimentation si nécessaire',
                'estimated_time': 15,
                'requires_tools': ['EPI complets', 'Détecteur de tension'],
                'requires_parts': [],
                'technical_level': 'basic',
                'safety_precautions': ['Port d\'EPI obligatoire', 'Vérification absence de tension'],
                'success_criteria': 'Site sécurisé pour intervention',
                'failure_indicators': ['Présence de tension résiduelle'],
                'cost_estimate': 0.0
            }
        ]

        if partie == 'onduleur':
            steps.append({
                'step': 2,
                'title': 'Diagnostic onduleur',
                'description': f"Inspection visuelle et tests de l'onduleur - {alarm_data.get('description', '')}",
                'estimated_time': 45,
                'requires_tools': ['Multimètre', 'Caméra thermique', 'Documentation'],
                'requires_parts': [],
                'technical_level': 'intermediate',
                'safety_precautions': ['Onduleur hors tension', 'Attendre refroidissement'],
                'success_criteria': 'Cause identifiée et documentée',
                'failure_indicators': ['Impossible d\'identifier la cause'],
                'cost_estimate': 0.0
            })

        return steps

    def _get_fallback_plan(self, alarm_data):
        """Plan de secours enrichi si l'IA échoue"""
        _logger.info("Génération du plan de secours enrichi")

        description_text = alarm_data.get('description', 'Aucune description disponible')
        severity = alarm_data.get('severity', 'unknown')
        occurrence_count = alarm_data.get('occurrence_count', 0)

        plan = {
            'diagnostic': f"Plan de secours pour l'alarme {alarm_data.get('code_alarm', 'Inconnu')} - {alarm_data.get('name', 'Inconnu')}. Sévérité: {severity}. Description: {description_text}.",
            'severity': 'medium',
            'estimated_resolution_time': 3.0,
            'requires_specialist': occurrence_count > 3,
            'confidence_score': 60,
            'risk_assessment': 'Risque modéré - Plan de secours appliqué',
            'action_steps': [
                {
                    'step': 1,
                    'title': 'Consultation documentation technique',
                    'description': f"Rechercher dans la documentation technique l'alarme {alarm_data.get('code_alarm', 'Inconnu')} avec description: {description_text}",
                    'estimated_time': 30,
                    'requires_tools': ['Documentation technique', 'Accès internet'],
                    'requires_parts': [],
                    'technical_level': 'basic',
                    'safety_precautions': ['Aucune intervention physique'],
                    'success_criteria': 'Procédure trouvée dans documentation',
                    'failure_indicators': ['Aucune référence trouvée'],
                    'cost_estimate': 0.0
                }
            ],
            'prevention_measures': [
                'Maintenance préventive trimestrielle',
                'Surveillance continue des performances'
            ],
            'monitoring_points': [
                'Surveillance alarmes 48h post-intervention',
                'Vérification performances hebdomadaire'
            ],
            'escalation_criteria': [
                'Réapparition de l\'alarme dans les 24h',
                'Plus de 3 occurrences en une semaine'
            ],
            'additional_notes': f'Plan de secours généré automatiquement. Occurrences: {occurrence_count}. Description: {description_text}.',
            'documentation_references': [
                'Manuel utilisateur équipement',
                'Guide de dépannage fabricant'
            ],
            'follow_up_actions': [
                'Documenter précisément la résolution',
                'Mettre à jour base de connaissances'
            ],
            'warranty_considerations': 'Vérifier validité garantie avant toute intervention physique',
            'environmental_factors': [
                'Conditions météorologiques actuelles',
                'Température ambiante et équipement'
            ]
        }

        plan['html_content'] = self._format_enhanced_action_plan_html(plan, alarm_data)
        return plan

    def _format_enhanced_action_plan_html(self, action_plan, alarm_data):
        """Formate le plan d'action enrichi en HTML"""
        severity_colors = {
            'low': '#28a745',
            'medium': '#ffc107',
            'high': '#fd7e14',
            'critical': '#dc3545'
        }

        severity_color = severity_colors.get(action_plan.get('severity', 'medium'), '#ffc107')
        confidence_score = action_plan.get('confidence_score', 70)

        html = f"""
        <div style="font-family: 'Segoe UI', sans-serif; max-width: 100%; background: #f8f9fa; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">

            <!-- En-tête avec métriques -->
            <div style="background: linear-gradient(135deg, {severity_color}15, {severity_color}05); padding: 20px; border-radius: 8px; border-left: 5px solid {severity_color}; margin-bottom: 20px;">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                    <div>
                        <h2 style="color: #2c3e50; margin: 0; font-size: 24px;">🔧 Plan d'Action Intelligent</h2>
                        <p style="color: #666; margin: 5px 0 0 0;">Alarme: {alarm_data.get('code_alarm', 'N/A')} - {alarm_data.get('name', 'N/A')}</p>
                    </div>
                    <div style="text-align: right;">
                        <div style="margin-bottom: 5px;">
                            <span style="background: {severity_color}; color: white; padding: 6px 12px; border-radius: 20px; font-weight: bold; font-size: 14px;">
                                {action_plan.get('severity', 'medium').upper()}
                            </span>
                        </div>
                        <div style="font-size: 12px; color: #666;">
                            ⏱️ {action_plan.get('estimated_resolution_time', 0):.1f}h • 
                            🎯 Confiance: {confidence_score}%
                        </div>
                    </div>
                </div>
            </div>

            <!-- Diagnostic et évaluation des risques -->
            <div style="background: white; padding: 20px; margin: 15px 0; border-radius: 8px; border-left: 4px solid {severity_color};">
                <h3 style="color: #2c3e50; margin-top: 0; display: flex; align-items: center;">
                    🔍 Diagnostic & Évaluation
                </h3>
                <div style="background: #f8f9fa; padding: 15px; border-radius: 6px; margin-bottom: 15px;">
                    <strong>Diagnostic:</strong>
                    <p style="margin: 8px 0 0 0; line-height: 1.6;">{action_plan.get('diagnostic', 'Non disponible')}</p>
                </div>
                <div style="background: #fff3cd; padding: 15px; border-radius: 6px; border-left: 3px solid #ffc107;">
                    <strong>⚠️ Évaluation des risques:</strong>
                    <p style="margin: 8px 0 0 0; line-height: 1.6;">{action_plan.get('risk_assessment', 'Non évaluée')}</p>
                </div>
            </div>

            <!-- Étapes de résolution -->
            <div style="background: white; padding: 20px; margin: 15px 0; border-radius: 8px;">
                <h3 style="color: #2c3e50; margin-top: 0;">📋 Plan de Résolution Détaillé</h3>
        """

        # Calcul du coût total
        total_cost = sum(step.get('cost_estimate', 0) for step in action_plan.get('action_steps', []))
        total_time = sum(step.get('estimated_time', 0) for step in action_plan.get('action_steps', []))

        if total_cost > 0 or total_time > 0:
            html += f"""
                <div style="background: #e8f5e8; padding: 12px; border-radius: 6px; margin-bottom: 15px; display: flex; justify-content: space-between;">
                    <span><strong>⏰ Durée totale estimée:</strong> {total_time} minutes</span>
                    <span><strong>💰 Coût estimé:</strong> {total_cost:.2f} €</span>
                </div>
            """

        for step in action_plan.get('action_steps', []):
            cost_estimate = step.get('cost_estimate', 0)
            html += f"""
                <div style="border: 1px solid #e9ecef; border-radius: 8px; padding: 18px; margin: 15px 0; background: #fdfdfd; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                    <div style="display: flex; align-items: center; margin-bottom: 12px;">
                        <span style="background: linear-gradient(135deg, #007bff, #0056b3); color: white; width: 35px; height: 35px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; margin-right: 15px; box-shadow: 0 2px 4px rgba(0,123,255,0.3);">
                            {step.get('step', '')}
                        </span>
                        <div style="flex-grow: 1;">
                            <h4 style="margin: 0; color: #2c3e50; font-size: 16px;">{step.get('title', '')}</h4>
                            <div style="font-size: 12px; color: #666; margin-top: 2px;">
                                Niveau: {step.get('technical_level', 'basic').title()} • 
                                Durée: {step.get('estimated_time', 0)} min
                            </div>
                        </div>
                    </div>

                    <div style="background: #f8f9fa; padding: 12px; border-radius: 6px; margin-bottom: 12px;">
                        <strong>📝 Description:</strong>
                        <p style="margin: 6px 0 0 0; line-height: 1.5; color: #495057;">{step.get('description', '')}</p>
                    </div>

                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 12px;">
                        <div style="background: #e8f4f8; padding: 10px; border-radius: 6px;">
                            <strong>✅ Critères de succès:</strong>
                            <div style="margin-top: 5px; font-size: 14px;">{step.get('success_criteria', 'Étape terminée')}</div>
                        </div>
                        <div style="background: #ffeaa7; padding: 10px; border-radius: 6px;">
                            <strong>❌ Indicateurs d'échec:</strong>
                            <div style="margin-top: 5px; font-size: 14px;">{', '.join(step.get('failure_indicators', ['Procédure non suivie']))}</div>
                        </div>
                    </div>
            """

            if step.get('requires_tools'):
                html += f"""
                    <div style="margin-bottom: 10px; padding: 10px; background: #e8f4f8; border-radius: 6px; border-left: 3px solid #17a2b8;">
                        <strong>🔧 Outils requis:</strong> {', '.join(step.get('requires_tools', []))}
                    </div>
                """

            if step.get('safety_precautions'):
                html += f"""
                    <div style="margin-bottom: 10px; padding: 10px; background: #fff3cd; border-radius: 6px; border-left: 3px solid #ffc107;">
                        <strong>⚠️ Précautions sécurité:</strong> {', '.join(step.get('safety_precautions', []))}
                    </div>
                """

            html += "</div>"

        html += "</div>"

        # Sections supplémentaires
        sections = [
            ('🛡️ Mesures Préventives', 'prevention_measures', '#e8f5e8'),
            ('📊 Points de Surveillance', 'monitoring_points', '#e3f2fd'),
            ('🔺 Critères d\'Escalade', 'escalation_criteria', '#ffebee'),
            ('📚 Références Documentation', 'documentation_references', '#fff8e1'),
            ('🔄 Actions de Suivi', 'follow_up_actions', '#f1f8e9')
        ]

        for title, key, bg_color in sections:
            if action_plan.get(key):
                html += f"""
                <div style="background: white; padding: 20px; margin: 15px 0; border-radius: 8px;">
                    <h3 style="color: #2c3e50; margin-top: 0;">{title}</h3>
                    <div style="background: {bg_color}; padding: 15px; border-radius: 6px;">
                        <ul style="margin: 0; padding-left: 20px; line-height: 1.6;">
                """
                for item in action_plan.get(key, []):
                    html += f"<li style='margin-bottom: 5px;'>{item}</li>"
                html += """
                        </ul>
                    </div>
                </div>
                """

        # Notes importantes et garantie
        if action_plan.get('additional_notes') or action_plan.get('warranty_considerations'):
            html += f"""
            <div style="background: #e9ecef; padding: 20px; margin: 15px 0; border-radius: 8px; border-left: 4px solid #6c757d;">
                <h3 style="color: #2c3e50; margin-top: 0;">📝 Informations Importantes</h3>
            """

            if action_plan.get('additional_notes'):
                html += f"""
                <div style="background: white; padding: 15px; border-radius: 6px; margin-bottom: 10px;">
                    <strong>Notes:</strong>
                    <p style="margin: 8px 0 0 0; line-height: 1.6;">{action_plan.get('additional_notes', '')}</p>
                </div>
                """

            if action_plan.get('warranty_considerations'):
                html += f"""
                <div style="background: #fff3cd; padding: 15px; border-radius: 6px; border-left: 3px solid #ffc107;">
                    <strong>🛡️ Considérations Garantie:</strong>
                    <p style="margin: 8px 0 0 0; line-height: 1.6;">{action_plan.get('warranty_considerations', '')}</p>
                </div>
                """

            html += "</div>"

        # Footer avec timestamp et métadonnées
        html += f"""
            <div style="background: #f8f9fa; padding: 15px; margin-top: 20px; border-radius: 8px; border-top: 2px solid {severity_color}; text-align: center; font-size: 12px; color: #666;">
                <div style="margin-bottom: 8px;">
                    <strong>Plan généré par IA</strong> • 
                    Confiance: {confidence_score}% • 
                    {action_plan.get('requires_specialist', False) and 'Spécialiste requis' or 'Intervention standard'}
                </div>
                <div>
                    📅 Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')} • 
                    🔄 Mise à jour recommandée si échec de résolution
                </div>
            </div>
        </div>
        """
        return html

    @api.model
    def debug_full_process(self):
        """Méthode de debug complète enrichie"""
        _logger.info("🚀 DEBUT DEBUG COMPLET ENRICHI")

        # Test 1: Clé API
        api_key = self._get_api_key()
        if not api_key:
            return "❌ Échec: Clé API non trouvée"

        # Test 2: Validation clé API
        is_valid, message = self._test_api_key()
        if not is_valid:
            return f"❌ Échec: {message}"

        # Test 3: Génération de plan enrichi avec description
        test_alarm_data = {
            'id': 1,
            'name': 'Test Alarm Enhanced',
            'partie': 'onduleur',
            'code_alarm': 'TEST001-ENH',
            'description': 'Alarme de test enrichie pour vérifier le fonctionnement complet du système IA avec toutes les nouvelles fonctionnalités',
            'severity': 'warning',
            'category': 'electrical',
            'occurrence_count': 3,
            'avg_resolution_time': 2.5,
            'resolution_rate': 75.0,
            'marque_onduleur': 'Test Brand Enhanced',
            'reclamations': [
                {
                    'date': '2024-01-15',
                    'description': 'Première occurrence test',
                    'installation_type': 'bt_commercial',
                    'priority': 'moyenne',
                    'has_intervention': True,
                    'intervention_state': 'closed',
                    'intervention_text': 'Résolu par remplacement fusible'
                }
            ]
        }

        plan = self.generate_alarm_action_plan(test_alarm_data)
        if not plan:
            return "❌ Échec: Génération de plan échouée"

        # Validation du plan enrichi
        required_keys = ['diagnostic', 'severity', 'action_steps', 'confidence_score', 'risk_assessment']
        missing_keys = [key for key in required_keys if key not in plan]

        if missing_keys:
            return f"⚠️ Plan généré mais clés manquantes: {', '.join(missing_keys)}"

        _logger.info("✅ DEBUG COMPLET ENRICHI RÉUSSI")
        return f"✅ Succès: Plan enrichi généré avec {len(plan.get('action_steps', []))} étapes, confiance {plan.get('confidence_score', 0)}%"