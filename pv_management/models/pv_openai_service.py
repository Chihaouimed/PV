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
            "max_tokens": 2000
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
        """Génère un plan d'action pour un code d'alarme"""
        try:
            _logger.info(f"Génération du plan d'action pour: {alarm_data.get('name', 'Inconnu')}")

            # Prompt système simplifié
            system_prompt = """
            Tu es un expert en maintenance d'installations photovoltaïques.
            Analyse le code d'alarme et génère un plan d'action détaillé.

            Réponds UNIQUEMENT avec un objet JSON valide dans ce format:
            {
                "diagnostic": "Description du problème identifié",
                "severity": "low"|"medium"|"high"|"critical",
                "estimated_resolution_time": 2.0,
                "requires_specialist": true|false,
                "action_steps": [
                    {
                        "step": 1,
                        "title": "Titre de l'étape",
                        "description": "Description détaillée de l'étape",
                        "estimated_time": 30,
                        "requires_tools": ["Multimètre", "Tournevis"],
                        "requires_parts": [],
                        "technical_level": "basic"|"intermediate"|"advanced",
                        "safety_precautions": ["Couper l'alimentation", "Porter des EPI"],
                        "success_criteria": "Comment savoir que l'étape est réussie"
                    }
                ],
                "prevention_measures": ["Maintenance préventive régulière"],
                "additional_notes": "Notes importantes",
                "documentation_references": ["Manuel utilisateur"],
                "follow_up_actions": ["Documenter la résolution"]
            }
            """

            user_prompt = f"""
            Code d'alarme à analyser:
            - Nom: {alarm_data.get('name', 'Inconnu')}
            - Code: {alarm_data.get('code_alarm', 'Inconnu')}
            - Partie concernée: {alarm_data.get('partie', 'Inconnu')}
            - Marque onduleur: {alarm_data.get('marque_onduleur', 'Non spécifiée')}

            Historique des réclamations: {len(alarm_data.get('reclamations', []))} occurence(s)

            Génère un plan d'action détaillé pour résoudre cette alarme.
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

            # Validation et nettoyage
            action_plan = self._validate_action_plan(action_plan)

            # Génération du HTML
            action_plan['html_content'] = self._format_action_plan_html(action_plan)

            return action_plan

        except Exception as e:
            _logger.error(f"Erreur dans generate_alarm_action_plan: {str(e)}")
            return self._get_fallback_plan(alarm_data)

    def _validate_action_plan(self, action_plan):
        """Valide et corrige le plan d'action"""
        # Valeurs par défaut
        defaults = {
            'diagnostic': 'Diagnostic automatique généré',
            'severity': 'medium',
            'estimated_resolution_time': 2.0,
            'requires_specialist': False,
            'action_steps': [],
            'prevention_measures': ['Maintenance préventive régulière'],
            'additional_notes': 'Plan généré automatiquement par IA',
            'documentation_references': ['Manuel utilisateur'],
            'follow_up_actions': ['Documenter la résolution']
        }

        # Appliquer les défauts si nécessaire
        for key, default_value in defaults.items():
            if key not in action_plan or not action_plan[key]:
                action_plan[key] = default_value

        # Validation des étapes
        if not action_plan['action_steps']:
            action_plan['action_steps'] = [
                {
                    'step': 1,
                    'title': 'Vérification initiale',
                    'description': 'Examiner l\'état général de l\'installation',
                    'estimated_time': 30,
                    'requires_tools': ['Multimètre', 'Documentation'],
                    'requires_parts': [],
                    'technical_level': 'basic',
                    'safety_precautions': ['Couper l\'alimentation', 'Porter des EPI'],
                    'success_criteria': 'État évalué'
                }
            ]

        return action_plan

    def _get_fallback_plan(self, alarm_data):
        """Plan de secours si l'IA échoue"""
        _logger.info("Génération du plan de secours")

        plan = {
            'diagnostic': f"Plan de secours pour l'alarme {alarm_data.get('code_alarm', 'Inconnu')} - {alarm_data.get('name', 'Inconnu')}. Consultez la documentation technique.",
            'severity': 'medium',
            'estimated_resolution_time': 2.0,
            'requires_specialist': True,
            'action_steps': [
                {
                    'step': 1,
                    'title': 'Consultation documentation',
                    'description': f"Consulter le manuel technique pour l'alarme {alarm_data.get('code_alarm', 'Inconnu')}",
                    'estimated_time': 30,
                    'requires_tools': ['Documentation technique', 'Multimètre'],
                    'requires_parts': [],
                    'technical_level': 'basic',
                    'safety_precautions': ['Couper l\'alimentation avant intervention'],
                    'success_criteria': 'Documentation consultée et comprise'
                },
                {
                    'step': 2,
                    'title': 'Contact support technique',
                    'description': 'Contacter le support technique du fabricant avec les détails de l\'alarme',
                    'estimated_time': 60,
                    'requires_tools': ['Téléphone', 'Informations installation'],
                    'requires_parts': [],
                    'technical_level': 'basic',
                    'safety_precautions': [],
                    'success_criteria': 'Support contacté et conseils obtenus'
                }
            ],
            'prevention_measures': [
                'Maintenance préventive régulière',
                'Surveillance continue des performances',
                'Formation du personnel technique'
            ],
            'additional_notes': 'Plan généré automatiquement. Pour un diagnostic plus précis, configurez l\'API OpenAI.',
            'documentation_references': ['Manuel utilisateur', 'Guide de dépannage fabricant'],
            'follow_up_actions': ['Documenter la résolution', 'Planifier maintenance préventive']
        }

        plan['html_content'] = self._format_action_plan_html(plan)
        return plan

    def _format_action_plan_html(self, action_plan):
        """Formate le plan d'action en HTML"""
        severity_colors = {
            'low': '#28a745',
            'medium': '#ffc107',
            'high': '#fd7e14',
            'critical': '#dc3545'
        }

        severity_color = severity_colors.get(action_plan.get('severity', 'medium'), '#ffc107')

        html = f"""
        <div style="font-family: 'Segoe UI', sans-serif; max-width: 100%; background: #f8f9fa; padding: 20px; border-radius: 8px;">
            <div style="text-align: center; margin-bottom: 20px;">
                <h2 style="color: #2c3e50; margin: 0;">🔧 Plan d'Action Intelligent</h2>
                <div style="margin-top: 10px;">
                    <span style="background: {severity_color}; color: white; padding: 5px 15px; border-radius: 15px; font-weight: bold;">
                        {action_plan.get('severity', 'medium').capitalize()}
                    </span>
                    <span style="margin-left: 15px; color: #666;">
                        ⏱️ {action_plan.get('estimated_resolution_time', 0):.1f}h estimées
                    </span>
                </div>
            </div>

            <div style="background: white; padding: 20px; margin: 15px 0; border-radius: 8px; border-left: 4px solid {severity_color};">
                <h3 style="color: #2c3e50; margin-top: 0;">🔍 Diagnostic</h3>
                <p style="line-height: 1.6; margin-bottom: 0;">{action_plan.get('diagnostic', 'Non disponible')}</p>
            </div>

            <div style="background: white; padding: 20px; margin: 15px 0; border-radius: 8px;">
                <h3 style="color: #2c3e50; margin-top: 0;">📋 Étapes de Résolution</h3>
        """

        for step in action_plan.get('action_steps', []):
            html += f"""
                <div style="border: 1px solid #e9ecef; border-radius: 6px; padding: 15px; margin: 10px 0; background: #fdfdfd;">
                    <div style="display: flex; align-items: center; margin-bottom: 10px;">
                        <span style="background: #007bff; color: white; width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; margin-right: 15px;">
                            {step.get('step', '')}
                        </span>
                        <h4 style="margin: 0; color: #2c3e50;">{step.get('title', '')}</h4>
                    </div>

                    <p style="margin: 10px 0; line-height: 1.5; color: #495057;">
                        <strong>Description:</strong> {step.get('description', '')}
                    </p>

                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 10px;">
                        <div>
                            <strong>⏰ Temps estimé:</strong> {step.get('estimated_time', 0)} minutes<br/>
                            <strong>🎯 Niveau:</strong> {step.get('technical_level', 'basic').capitalize()}
                        </div>
                        <div>
                            <strong>✅ Succès si:</strong> {step.get('success_criteria', 'Étape terminée')}
                        </div>
                    </div>
            """

            if step.get('requires_tools'):
                html += f"""
                    <div style="margin-top: 10px; padding: 8px; background: #e8f4f8; border-radius: 4px;">
                        <strong>🔧 Outils:</strong> {', '.join(step.get('requires_tools', []))}
                    </div>
                """

            if step.get('safety_precautions'):
                html += f"""
                    <div style="margin-top: 8px; padding: 8px; background: #fff3cd; border-left: 3px solid #ffc107; border-radius: 0 4px 4px 0;">
                        <strong>⚠️ Sécurité:</strong> {', '.join(step.get('safety_precautions', []))}
                    </div>
                """

            html += "</div>"

        html += "</div>"

        if action_plan.get('prevention_measures'):
            html += f"""
            <div style="background: white; padding: 20px; margin: 15px 0; border-radius: 8px;">
                <h3 style="color: #2c3e50; margin-top: 0;">🛡️ Prévention</h3>
                <ul style="line-height: 1.6;">
            """
            for measure in action_plan.get('prevention_measures', []):
                html += f"<li>{measure}</li>"
            html += "</ul></div>"

        if action_plan.get('additional_notes'):
            html += f"""
            <div style="background: #e9ecef; padding: 15px; margin: 15px 0; border-radius: 8px;">
                <h4 style="margin-top: 0;">📝 Notes Importantes</h4>
                <p style="margin-bottom: 0; line-height: 1.6;">{action_plan.get('additional_notes', '')}</p>
            </div>
            """

        html += "</div>"
        return html

    @api.model
    def debug_full_process(self):
        """Méthode de debug complète"""
        _logger.info("🚀 DEBUT DEBUG COMPLET")

        # Test 1: Clé API
        api_key = self._get_api_key()
        if not api_key:
            return "❌ Échec: Clé API non trouvée"

        # Test 2: Validation clé API
        is_valid, message = self._test_api_key()
        if not is_valid:
            return f"❌ Échec: {message}"

        # Test 3: Génération de plan simple
        test_alarm_data = {
            'id': 1,
            'name': 'Test Alarm',
            'partie': 'onduleur',
            'code_alarm': 'TEST001',
            'marque_onduleur': 'Test Brand',
            'reclamations': []
        }

        plan = self.generate_alarm_action_plan(test_alarm_data)
        if not plan:
            return "❌ Échec: Génération de plan échouée"

        _logger.info("✅ DEBUG COMPLET RÉUSSI")
        return f"✅ Succès: Plan généré avec {len(plan.get('action_steps', []))} étapes"