from odoo import models, fields, api
import json
import logging
from datetime import datetime, timedelta
import requests
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PVOpenAIService(models.AbstractModel):
    _name = 'pv.management.openai.service'
    _description = 'Service d\'intégration OpenAI pour la gestion des installations PV'

    @api.model
    def _make_openai_request(self, messages, model="gpt-4o-mini", temperature=0.7):
        """Make a request to OpenAI API using requests library"""
        # Récupérer la clé API depuis les paramètres système
        api_key = self.env['ir.config_parameter'].sudo().get_param('pv_management.openai_api_key')
        if not api_key:
            _logger.warning("Clé API OpenAI non configurée")
            return False

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"}
        }

        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()  # Raise an exception for 4XX/5XX status codes

            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                return result['choices'][0]['message']['content']
            else:
                _logger.error(f"Unexpected API response format: {result}")
                return False

        except requests.exceptions.RequestException as e:
            _logger.error(f"Error making request to OpenAI API: {str(e)}")
            return False

    @api.model
    def generate_alarm_action_plan(self, alarm_data):
        """
        Génère un plan d'action basé sur le code d'alarme
        :param alarm_data: dictionnaire contenant les données d'alarme
        :return: dictionnaire avec le plan d'action
        """
        try:
            # Préparer le prompt pour OpenAI
            system_prompt = """
            Tu es un expert en maintenance d'installations photovoltaïques et en résolution de problèmes.
            Analyse les données d'alarme fournies pour générer un plan d'action détaillé pour résoudre le problème.

            Le plan d'action doit inclure:
            1. Un diagnostic du problème basé sur le code d'alarme
            2. Des étapes détaillées de dépannage et de résolution
            3. Une estimation de la gravité du problème
            4. Des pièces ou outils nécessaires pour la réparation
            5. Des mesures préventives pour éviter que ce problème ne se reproduise

            Réponds en français avec un objet JSON structuré exactement comme ceci:
            {
                "diagnostic": string,  # Diagnostic du problème
                "severity": "low"|"medium"|"high"|"critical",  # Gravité du problème
                "estimated_resolution_time": int,  # Temps estimé de résolution en heures
                "requires_specialist": boolean,  # Nécessite un spécialiste
                "action_steps": [  # Étapes d'action détaillées
                    {
                        "step": int,  # Numéro d'étape
                        "description": string,  # Description détaillée
                        "estimated_time": int,  # Temps estimé en minutes
                        "requires_tools": [string],  # Outils nécessaires
                        "requires_parts": [string],  # Pièces nécessaires
                        "technical_level": "basic"|"intermediate"|"advanced",  # Niveau technique requis
                        "safety_precautions": [string]  # Précautions de sécurité
                    },
                    ...
                ],
                "prevention_measures": [string],  # Mesures préventives
                "additional_notes": string,  # Notes supplémentaires
                "documentation_references": [string]  # Références à la documentation
            }
            """

            user_prompt = f"""
            Voici les données d'alarme à analyser:
            {json.dumps(alarm_data, indent=2, ensure_ascii=False)}

            Analyse ce code d'alarme en tenant compte du type d'installation, de la marque de l'onduleur ou du module,
            et de toute information historique sur des problèmes similaires si disponible.

            Fournis un plan d'action détaillé pour résoudre le problème en fonction du contexte spécifique.

            Réponds uniquement avec l'objet JSON demandé.
            """

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            content = self._make_openai_request(messages)
            if not content:
                return False

            action_plan = json.loads(content) if content is not None else {}

            # Validation et nettoyage des données
            if 'diagnostic' not in action_plan:
                _logger.warning("'diagnostic' manquant dans la réponse OpenAI")
                action_plan['diagnostic'] = "Diagnostic non disponible."

            if 'severity' not in action_plan:
                _logger.warning("'severity' manquant dans la réponse OpenAI")
                action_plan['severity'] = 'medium'

            if 'action_steps' not in action_plan:
                _logger.warning("'action_steps' manquant dans la réponse OpenAI")
                action_plan['action_steps'] = []

            if 'prevention_measures' not in action_plan:
                _logger.warning("'prevention_measures' manquant dans la réponse OpenAI")
                action_plan['prevention_measures'] = []

            # Formater le plan d'action en HTML pour l'affichage
            action_plan['html_content'] = self._format_action_plan_html(action_plan)

            return action_plan

        except Exception as e:
            _logger.error(f"Erreur dans generate_alarm_action_plan: {str(e)}")
            return False

    def _format_action_plan_html(self, action_plan):
        """
        Formate le plan d'action en HTML pour l'affichage
        :param action_plan: dictionnaire contenant le plan d'action
        :return: chaîne HTML formatée
        """
        html = f"""
        <div class="action-plan">
            <div class="diagnostic-section">
                <h3>Diagnostic</h3>
                <p>{action_plan.get('diagnostic', 'Non disponible')}</p>

                <div class="severity-box severity-{action_plan.get('severity', 'medium')}">
                    <strong>Gravité:</strong> {action_plan.get('severity', 'medium').capitalize()}
                </div>

                <div class="details-box">
                    <div><strong>Temps estimé:</strong> {action_plan.get('estimated_resolution_time', 'N/A')} heure(s)</div>
                    <div><strong>Spécialiste requis:</strong> {'Oui' if action_plan.get('requires_specialist', False) else 'Non'}</div>
                </div>
            </div>

            <div class="steps-section">
                <h3>Plan d'action</h3>
                <ol>
        """

        for step in action_plan.get('action_steps', []):
            html += f"""
                    <li>
                        <div class="step-box">
                            <div class="step-header">
                                <strong>{step.get('description', '')}</strong>
                                <span class="tech-level tech-level-{step.get('technical_level', 'basic')}">
                                    {step.get('technical_level', 'basic').capitalize()}
                                </span>
                            </div>
                            <div class="step-details">
                                <div><strong>Temps estimé:</strong> {step.get('estimated_time', 'N/A')} minutes</div>
            """

            if step.get('requires_tools'):
                html += f"""
                                <div class="tools">
                                    <strong>Outils nécessaires:</strong>
                                    <ul>
                """
                for tool in step.get('requires_tools', []):
                    html += f"""
                                        <li>{tool}</li>
                    """
                html += """
                                    </ul>
                                </div>
                """

            if step.get('requires_parts'):
                html += f"""
                                <div class="parts">
                                    <strong>Pièces nécessaires:</strong>
                                    <ul>
                """
                for part in step.get('requires_parts', []):
                    html += f"""
                                        <li>{part}</li>
                    """
                html += """
                                    </ul>
                                </div>
                """

            if step.get('safety_precautions'):
                html += f"""
                                <div class="safety-warnings">
                                    <strong>Précautions de sécurité:</strong>
                                    <ul>
                """
                for precaution in step.get('safety_precautions', []):
                    html += f"""
                                        <li>{precaution}</li>
                    """
                html += """
                                    </ul>
                                </div>
                """

            html += """
                            </div>
                        </div>
                    </li>
            """

        html += """
                </ol>
            </div>
        """

        if action_plan.get('prevention_measures'):
            html += """
            <div class="prevention-section">
                <h3>Mesures préventives</h3>
                <ul>
            """
            for measure in action_plan.get('prevention_measures', []):
                html += f"""
                    <li>{measure}</li>
                """
            html += """
                </ul>
            </div>
            """

        if action_plan.get('additional_notes'):
            html += f"""
            <div class="notes-section">
                <h3>Notes supplémentaires</h3>
                <p>{action_plan.get('additional_notes', '')}</p>
            </div>
            """

        if action_plan.get('documentation_references'):
            html += """
            <div class="documentation-section">
                <h3>Références</h3>
                <ul>
            """
            for ref in action_plan.get('documentation_references', []):
                html += f"""
                    <li>{ref}</li>
                """
            html += """
                </ul>
            </div>
            """

        html += """
        </div>
        <style>
            .action-plan {
                font-family: 'Roboto', sans-serif;
                color: #333;
                max-width: 100%;
            }
            .diagnostic-section, .steps-section, .prevention-section, .notes-section, .documentation-section {
                margin-bottom: 20px;
                padding: 15px;
                background-color: #f9f9f9;
                border-radius: 5px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }
            .severity-box {
                display: inline-block;
                padding: 5px 10px;
                border-radius: 4px;
                color: white;
                font-weight: bold;
                margin: 10px 0;
            }
            .severity-low { background-color: #28a745; }
            .severity-medium { background-color: #ffc107; color: #333; }
            .severity-high { background-color: #fd7e14; }
            .severity-critical { background-color: #dc3545; }

            .details-box {
                display: flex;
                justify-content: space-between;
                flex-wrap: wrap;
                margin: 10px 0;
            }
            .details-box > div {
                flex-basis: 48%;
                margin-bottom: 5px;
            }

            .step-box {
                background-color: white;
                border-radius: 4px;
                padding: 10px;
                margin-bottom: 10px;
                box-shadow: 0 1px 2px rgba(0,0,0,0.05);
            }
            .step-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 8px;
                border-bottom: 1px solid #eee;
                padding-bottom: 8px;
            }
            .step-details {
                padding-left: 10px;
                border-left: 2px solid #eee;
            }
            .tech-level {
                padding: 2px 8px;
                border-radius: 3px;
                font-size: 0.8em;
            }
            .tech-level-basic { background-color: #e9ecef; }
            .tech-level-intermediate { background-color: #cce5ff; }
            .tech-level-advanced { background-color: #f8d7da; }

            .safety-warnings {
                margin-top: 8px;
                padding: 8px;
                background-color: #fff3cd;
                border-left: 3px solid #ffc107;
                border-radius: 0 3px 3px 0;
            }

            h3 {
                color: #0069d9;
                border-bottom: 1px solid #eee;
                padding-bottom: 5px;
            }

            ul, ol {
                padding-left: 20px;
            }

            .tools, .parts {
                margin-top: 5px;
            }
        </style>
        """

        return html