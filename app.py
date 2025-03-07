from flask import Flask, render_template, jsonify, request, url_for, redirect
import logging
from utilities.logger import configure_logging
import threading
from main import run_pipeline
from datetime import datetime, timedelta
from scrapers.perplexity_client import PerplexityClient
import os
from dotenv import load_dotenv
from utilities.email_handler import EmailHandler
from whatsapp.interakt_handler import InteraktHandler
from config.settings import Config
import json

app = Flask(__name__)
configure_logging()
logger = logging.getLogger(__name__)
load_dotenv()

# Store the last run time and status
last_run_time = None
is_running = False
last_run_status = None
last_run_results = None

# Initialize Perplexity client
perplexity_client = PerplexityClient()

# Store project data and chat contexts
project_data = {}
chat_contexts = {}

# In-memory storage for projects (replace with database in production)
projects = []

# Initialize handlers
whatsapp_handler = InteraktHandler()


@app.route('/')
def index():
    """Home page with run button"""
    return render_template('index.html',
                           last_run_time=last_run_time,
                           is_running=is_running,
                           last_run_status=last_run_status,
                           last_run_results=last_run_results)


@app.route('/chat')
def chat_interface():
    """Chat interface for project discovery"""
    return render_template('chat.html')


@app.route('/projects')
def projects_list():
    # Get filter parameters
    project_type = request.args.get('type')
    value_range = request.args.get('value')
    timeline = request.args.get('timeline')
    sort_by = request.args.get('sort')

    filtered_projects = projects.copy()

    # Apply filters
    if project_type:
        filtered_projects = [
            p for p in filtered_projects if p['type'] == project_type]

    if value_range:
        min_val, max_val = map(float, value_range.split('-'))
        filtered_projects = [
            p for p in filtered_projects if min_val <= p['value'] <= max_val]

    if timeline:
        months = int(timeline.split('-')[0])
        cutoff_date = datetime.now() + timedelta(days=30*months)
        filtered_projects = [
            p for p in filtered_projects if p['start_date'] <= cutoff_date]

    # Apply sorting
    if sort_by:
        reverse = sort_by.endswith('-desc')
        key = sort_by.split('-')[0]
        filtered_projects.sort(key=lambda x: x[key], reverse=reverse)

    return render_template('projects.html', projects=filtered_projects)


@app.route('/project/<project_id>')
def project_details(project_id):
    # Find project by ID (company_title)
    project = next(
        (p for p in projects if f"{p['company']}_{p['title'].lower().replace(' ', '_')}" == project_id), None)

    if not project:
        return "Project not found", 404

    return render_template('project_details.html', project=project)


@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    project_id = data.get('project_id')
    message = data.get('message')

    # If no project_id, this is a general chat
    if not project_id:
        response = perplexity_client.get_project_info(message)
        return jsonify({"response": response})

    # Find project context
    project = next(
        (p for p in projects if f"{p['company']}_{p['title'].lower().replace(' ', '_')}" == project_id), None)

    if not project:
        return jsonify({"error": "Project not found"}), 404

    # Create context for the AI
    context = f"""
    Project: {project['title']}
    Company: {project['company']}
    Value: ₹{project['value']} Crore
    Timeline: {project['start_date'].strftime('%B %d, %Y')} to {project['end_date'].strftime('%B %d, %Y')}
    Description: {project['description']}
    Source: {project['source_url']}
    """

    # Get AI response using Perplexity
    response = perplexity_client.get_project_info(
        context + "\n\nUser question: " + message)
    return jsonify({"response": response})


@app.route('/api/projects', methods=['POST'])
def update_projects():
    """Update projects data from the pipeline"""
    data = request.json
    if not isinstance(data, list):
        return jsonify({"error": "Expected a list of projects"}), 400

    # Convert string dates to datetime objects
    for project in data:
        project['start_date'] = datetime.strptime(
            project['start_date'], '%Y-%m-%d')
        project['end_date'] = datetime.strptime(
            project['end_date'], '%Y-%m-%d')

    # Update global projects list
    global projects
    projects = data

    return jsonify({"message": "Projects updated successfully", "count": len(projects)})


@app.route('/run', methods=['POST'])
def run_script():
    """Endpoint to trigger the main script"""
    global is_running, last_run_time, last_run_status, last_run_results

    if is_running:
        return jsonify({
            'status': 'error',
            'message': 'Script is already running'
        }), 400

    def run_task():
        global is_running, last_run_time, last_run_status, last_run_results
        try:
            is_running = True
            last_run_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            last_run_status = 'running'
            last_run_results = None

            # Run the pipeline
            run_pipeline()

            last_run_status = 'completed'
            last_run_results = 'Pipeline completed successfully'

        except Exception as e:
            logger.error(f"Error running pipeline: {str(e)}", exc_info=True)
            last_run_status = 'failed'
            last_run_results = f"Error: {str(e)}"

        finally:
            is_running = False

    # Start the task in a background thread
    thread = threading.Thread(target=run_task)
    thread.start()

    return jsonify({
        'status': 'success',
        'message': 'Script started successfully'
    })


@app.route('/get-members', methods=['GET'])
def get_members():
    """Get team members"""

    return jsonify({
        'status': 'success',
        'message': 'Team members fetched successfully',
        'members': Config.TEAM_MEMBERS
    })


@app.route('/add-member', methods=['POST'])
def add_member():
    """Adds team member to the team"""

    def add_member():
        global team
        try:
            team = request.get_json()
            print(team)

            Config.TEAM_MEMBERS[team["team"]].append(team)

        except Exception as e:
            logger.error(f"Error running pipeline: {str(e)}", exc_info=True)

    add_member()

    return jsonify({
        'status': 'success',
        'message': 'Script started successfully' + json.dumps(Config.TEAM_MEMBERS)
    })


@app.route('/remove-member', methods=['POST'])
def remove_member():
    """Removes team member to the team"""

    def remove_member():
        global team
        try:
            team = request.get_json()

            Config.TEAM_MEMBERS[team["team"]].remove(team)

        except Exception as e:
            logger.error(f"Error running pipeline: {str(e)}", exc_info=True)

    remove_member()

    return jsonify({
        'status': 'success',
        'message': 'Script started successfully' + json.dumps(Config.TEAM_MEMBERS)
    })


@app.route('/save-workflow-settings', methods=['POST'])
def save_workflow_settings():
    """Save workflow settings"""

    def save_workflow_settings():
        try:
            Config.WORKFLOW_SETTINGS = request.get_json()

        except Exception as e:
            logger.error(
                f"Error saving workflow settings: {str(e)}", exc_info=True)
    save_workflow_settings()
    return jsonify({
        'status': 'success',
        'message': 'Workflow settings saved successfully',
        'settings': Config.WORKFLOW_SETTINGS
    })


@app.route('/get-workflow-settings', methods=['GET'])
def get_workflow_settings():
    """Get workflow settings"""

    return jsonify({
        'status': 'success',
        'message': 'Workflow settings fetched successfully',
        'settings': Config.WORKFLOW_SETTINGS
    })


@app.route('/status')
def get_status():
    """Get the current status of the script"""
    return jsonify({
        'is_running': is_running,
        'last_run_time': last_run_time,
        'status': last_run_status,
        'results': last_run_results
    })


@app.route('/api/project/<project_id>')
def get_project_info(project_id):
    """Get project information for the chat interface"""
    # This is test data - in production, you would fetch this from your database
    test_projects = {
        'larsen_toubro_mumbai_metro_project': {
            'company': 'Larsen & Toubro',
            'title': 'Mumbai Metro Project',
            'value': 500.0,
            'steel_requirement': 400,
            'timeline': 'Q3, 2024 - 3 years',
            'contacts': [
                {
                    'name': 'Ashish Raheja',
                    'role': 'VP, Eng. Procurement',
                    'phone': '+91 9898439394',
                    'email': 'ashish.raheja@rahee.com'
                },
                {
                    'name': 'Boman Irani',
                    'role': 'Senior VP, Procurement',
                    'phone': '+91 9074598939',
                    'email': 'boman.irani@rahee.com'
                }
            ]
        },
        'rahee_infra_delhi_viaduct': {
            'company': 'Rahee Infratech',
            'title': 'Delhi Metro Viaduct Construction',
            'value': 350.0,
            'steel_requirement': 280,
            'timeline': 'Q4, 2024 - 2 years',
            'contacts': [
                {
                    'name': 'Rajesh Kumar',
                    'role': 'Project Director',
                    'phone': '+91 9876543210',
                    'email': 'rajesh.kumar@rahee.com'
                }
            ]
        },
        'hg_infra_new_delhi_railway_station_revamp': {
            'title': 'HG Infra wins New Delhi railway station revamp contract (with DEC Infra)',
            'company': 'HG Infra',
            'value': 2196,  # Rs. 2196 Crore
            'description': 'HG Infra has secured the EPC contract for New Delhi railway station redevelopment project. JSW Steel has previously supplied TMT bars and other products to HG infra for expressway projects.',
            'start_date': datetime.now() + timedelta(days=365),  # Q4 2025
            'end_date': datetime.now() + timedelta(days=365 + (45 * 30)),  # 45 months duration
            'source': 'cnbctv18.com',
            'source_url': 'https://www.cnbctv18.com/market/stocks/hg-infra-engineering-share-price-wins-rs-2196-crore-epc-contract-for-new-delhi-railway-station-redevelopment-19556883.htm',
            'teams': ['TMT_BARS'],
            'steel_requirements': {
                'primary': {'type': 'TMT Bars', 'quantity': 15000},
                'secondary': {'type': 'HR Plates', 'quantity': 8000},
                'total': 23000
            },
            'contacts': [{
                'name': 'Ajay Kumar Sharma',
                'role': 'Procurement for Infrastructure & Construction',
                'email': 'ajay.kumar@hginfra.com',
                'phone': '+919509699014'
            }],
            'priority_score': 85,  # High priority score
            'final_priority_score': 85,  # Added for email template
            'tags': ['High Priority'],
            'relationship_notes': 'JSW Steel has previously supplied TMT bars and other products to HG infra for expressway projects.'
        }
    }

    # Get project info or return default test data
    project_info = test_projects.get(project_id, {
        'company': project_id.replace('_', ' ').title(),
        'title': 'Test Project',
        'value': 100.0,
        'steel_requirement': 80,
        'timeline': 'Q1, 2024 - 1 year'
    })

    return jsonify(project_info)


@app.route('/send_test_email')
def send_test_email():
    """Send test emails with sample project leads to respective teams"""
    try:
        email_handler = EmailHandler()

        # Test projects for different teams
        test_projects = [
            # Solar project
            {
                'title': 'Gensol Wins Contract for 245 MW Solar Project at Gujarat\'s Khavda RE Park',
                'company': 'Gensol EPC',
                'value': 967,
                'description': 'Gensol has secured a 245 MW solar project contract at Gujarat\'s Khavda RE Park.',
                'start_date': datetime.now() + timedelta(days=30),
                'end_date': datetime.now() + timedelta(days=365),
                'source': 'constructionworld.in',
                'source_url': 'https://www.constructionworld.in/energy-infrastructure/power-and-renewable-energy/gensol-wins-rs-9.67-billion-epc-contract-for-245-mw-solar-project/68842',
                'teams': ['SOLAR'],
                'steel_requirements': {
                    'primary': {'type': 'Solar Solutions', 'quantity': 15000},
                    'total': 15000
                },
                'contacts': [{
                    'name': 'Dushyant Kumar',
                    'role': 'Chief Procurement Officer - Gensol EPC (India)',
                    'email': 'dushyantkumar@gensol.in',
                    'phone': '+919818793531'
                }],
                'priority_score': 85,
                'final_priority_score': 85,
                'tags': ['High Priority']
            },
            # TMT Bars project
            {
                'title': 'HG Infra wins New Delhi railway station revamp contract (with DEC Infra)',
                'company': 'HG Infra',
                'value': 2196,
                'description': 'HG Infra has secured the EPC contract for New Delhi railway station redevelopment project.',
                'start_date': datetime.now() + timedelta(days=365),  # Q4 2025
                'end_date': datetime.now() + timedelta(days=365 + (45 * 30)),  # 45 months duration
                'source': 'cnbctv18.com',
                'source_url': 'https://www.cnbctv18.com/market/stocks/hg-infra-engineering-share-price-wins-rs-2196-crore-epc-contract-for-new-delhi-railway-station-redevelopment-19556883.htm',
                'teams': ['TMT_BARS'],
                'steel_requirements': {
                    'primary': {'type': 'TMT Bars', 'quantity': 15000},
                    'secondary': {'type': 'HR Plates', 'quantity': 8000},
                    'total': 23000
                },
                'contacts': [{
                    'name': 'Ajay Kumar Sharma',
                    'role': 'Procurement for Infrastructure & Construction',
                    'email': 'ajay.kumar@hginfra.com',
                    'phone': '+919509699014'
                }],
                'priority_score': 85,
                'final_priority_score': 85,
                'tags': ['High Priority'],
                'relationship_notes': 'JSW Steel has previously supplied TMT bars and other products to HG infra for expressway projects.'
            },
            # Hot Rolled project
            {
                'title': 'Tata Projects Secures Order for Steel Plant Expansion in Odisha',
                'company': 'Tata Projects',
                'value': 3500,
                'description': 'Tata Projects has secured an order for the expansion of a steel plant in Odisha, requiring significant hot rolled steel products.',
                'start_date': datetime.now() + timedelta(days=90),
                'end_date': datetime.now() + timedelta(days=90 + (24 * 30)),  # 24 months duration
                'source': 'economictimes.indiatimes.com',
                'source_url': 'https://economictimes.indiatimes.com/industry/indl-goods/svs/engineering/tata-projects-wins-significant-order-for-steel-plant-expansion/articleshow/example.cms',
                'teams': ['HOT_ROLLED'],
                'steel_requirements': {
                    'primary': {'type': 'Hot Rolled Coils', 'quantity': 25000},
                    'secondary': {'type': 'HR Plates', 'quantity': 10000},
                    'total': 35000
                },
                'contacts': [{
                    'name': 'Rajiv Mehta',
                    'role': 'Director - Procurement',
                    'email': 'rajiv.mehta@tataprojects.com',
                    'phone': '+919876543210'
                }],
                'priority_score': 90,
                'final_priority_score': 90,
                'tags': ['High Priority'],
                'relationship_notes': 'JSW Steel has previously supplied hot rolled products to Tata Projects for industrial projects.'
            },
            # Cold Rolled project
            {
                'title': 'Maruti Suzuki Announces New Manufacturing Facility in Gujarat',
                'company': 'Maruti Suzuki India Ltd',
                'value': 7500,
                'description': 'Maruti Suzuki is setting up a new manufacturing facility in Gujarat with significant requirements for cold rolled steel products.',
                'start_date': datetime.now() + timedelta(days=180),
                'end_date': datetime.now() + timedelta(days=180 + (36 * 30)),  # 36 months duration
                'source': 'business-standard.com',
                'source_url': 'https://www.business-standard.com/article/companies/maruti-suzuki-to-set-up-new-manufacturing-facility-in-gujarat-example',
                'teams': ['COLD_ROLLED'],
                'steel_requirements': {
                    'primary': {'type': 'Cold Rolled Coils', 'quantity': 30000},
                    'secondary': {'type': 'Galvanized Steel', 'quantity': 15000},
                    'total': 45000
                },
                'contacts': [{
                    'name': 'Amit Patel',
                    'role': 'Senior VP - Supply Chain',
                    'email': 'amit.patel@maruti.co.in',
                    'phone': '+919898765432'
                }],
                'priority_score': 85,
                'final_priority_score': 85,
                'tags': ['High Priority'],
                'relationship_notes': 'JSW Steel is a preferred supplier for Maruti Suzuki\'s automotive steel requirements.'
            },
            # Galvanized project
            {
                'title': 'Adani Group Wins Contract for Airport Terminal Construction in Mumbai',
                'company': 'Adani Enterprises',
                'value': 5800,
                'description': 'Adani Group has secured a contract for the construction of a new terminal at Mumbai International Airport with significant galvanized steel requirements.',
                'start_date': datetime.now() + timedelta(days=120),
                'end_date': datetime.now() + timedelta(days=120 + (30 * 30)),  # 30 months duration
                'source': 'livemint.com',
                'source_url': 'https://www.livemint.com/companies/news/adani-group-wins-contract-for-mumbai-airport-terminal-example',
                'teams': ['GALVANIZED'],
                'steel_requirements': {
                    'primary': {'type': 'Galvanized Steel', 'quantity': 18000},
                    'secondary': {'type': 'Cold Rolled Steel', 'quantity': 7000},
                    'total': 25000
                },
                'contacts': [{
                    'name': 'Vikram Joshi',
                    'role': 'Head of Procurement',
                    'email': 'vikram.joshi@adani.com',
                    'phone': '+919876123456'
                }],
                'priority_score': 80,
                'final_priority_score': 80,
                'tags': ['High Priority'],
                'relationship_notes': 'JSW Steel has previously supplied galvanized products to Adani Group for infrastructure projects.'
            },
            # Electrical Steel project
            {
                'title': 'BHEL Secures Order for Power Transformer Manufacturing Plant',
                'company': 'Bharat Heavy Electricals Limited',
                'value': 1200,
                'description': 'BHEL has secured an order for setting up a power transformer manufacturing plant requiring significant electrical steel.',
                'start_date': datetime.now() + timedelta(days=60),
                'end_date': datetime.now() + timedelta(days=60 + (18 * 30)),  # 18 months duration
                'source': 'financialexpress.com',
                'source_url': 'https://www.financialexpress.com/industry/bhel-bags-order-for-power-transformer-plant-example',
                'teams': ['ELECTRICAL_STEEL'],
                'steel_requirements': {
                    'primary': {'type': 'Electrical Steel', 'quantity': 8000},
                    'total': 8000
                },
                'contacts': [{
                    'name': 'Suresh Kumar',
                    'role': 'General Manager - Materials',
                    'email': 'suresh.kumar@bhel.in',
                    'phone': '+919123456789'
                }],
                'priority_score': 75,
                'final_priority_score': 75,
                'tags': ['High Priority'],
                'relationship_notes': 'JSW Steel has been supplying electrical steel to BHEL for various power projects.'
            },
            # Galvalume Steel project
            {
                'title': 'Godrej Properties Announces Township Project in Pune',
                'company': 'Godrej Properties',
                'value': 3200,
                'description': 'Godrej Properties has announced a new township project in Pune with significant requirements for galvalume steel roofing.',
                'start_date': datetime.now() + timedelta(days=90),
                'end_date': datetime.now() + timedelta(days=90 + (48 * 30)),  # 48 months duration
                'source': 'economictimes.indiatimes.com',
                'source_url': 'https://economictimes.indiatimes.com/industry/services/property-/-cstruction/godrej-properties-announces-township-project-in-pune-example',
                'teams': ['GALVALUME_STEEL'],
                'steel_requirements': {
                    'primary': {'type': 'Galvalume Steel', 'quantity': 12000},
                    'secondary': {'type': 'Color Coated Steel', 'quantity': 5000},
                    'total': 17000
                },
                'contacts': [{
                    'name': 'Priya Sharma',
                    'role': 'VP - Procurement',
                    'email': 'priya.sharma@godrejproperties.com',
                    'phone': '+919876543210'
                }],
                'priority_score': 70,
                'final_priority_score': 70,
                'tags': ['Normal Priority'],
                'relationship_notes': 'JSW Steel has previously supplied galvalume products to Godrej Properties for residential projects.'
            },
            # Wire Rods project
            {
                'title': 'KEC International Wins Order for Transmission Line Project',
                'company': 'KEC International',
                'value': 1800,
                'description': 'KEC International has secured an order for a major transmission line project requiring significant wire rod products.',
                'start_date': datetime.now() + timedelta(days=45),
                'end_date': datetime.now() + timedelta(days=45 + (24 * 30)),  # 24 months duration
                'source': 'business-standard.com',
                'source_url': 'https://www.business-standard.com/article/companies/kec-international-wins-new-orders-worth-rs-1800-crore-example',
                'teams': ['WIRE_RODS'],
                'steel_requirements': {
                    'primary': {'type': 'Wire Rods', 'quantity': 9000},
                    'total': 9000
                },
                'contacts': [{
                    'name': 'Rahul Gupta',
                    'role': 'Director - Supply Chain',
                    'email': 'rahul.gupta@kecindia.com',
                    'phone': '+919876543210'
                }],
                'priority_score': 80,
                'final_priority_score': 80,
                'tags': ['High Priority'],
                'relationship_notes': 'JSW Steel has been a key supplier of wire rods to KEC International for transmission projects.'
            },
            # Special Alloy Steel project
            {
                'title': 'Larsen & Toubro Secures Defense Manufacturing Contract',
                'company': 'Larsen & Toubro',
                'value': 4500,
                'description': 'L&T has secured a defense manufacturing contract requiring high-grade special alloy steel products.',
                'start_date': datetime.now() + timedelta(days=120),
                'end_date': datetime.now() + timedelta(days=120 + (36 * 30)),  # 36 months duration
                'source': 'livemint.com',
                'source_url': 'https://www.livemint.com/companies/news/l-t-bags-defence-manufacturing-contract-example',
                'teams': ['SPECIAL_ALLOY_STEEL'],
                'steel_requirements': {
                    'primary': {'type': 'Special Alloy Steel', 'quantity': 7000},
                    'secondary': {'type': 'High-Strength Steel', 'quantity': 3000},
                    'total': 10000
                },
                'contacts': [{
                    'name': 'Sanjay Mehta',
                    'role': 'Chief Procurement Officer',
                    'email': 'sanjay.mehta@larsentoubro.com',
                    'phone': '+919876543210'
                }],
                'priority_score': 85,
                'final_priority_score': 85,
                'tags': ['High Priority'],
                'relationship_notes': 'JSW Steel has previously supplied special alloy steel to L&T for defense and heavy engineering projects.'
            },
            # Metro project with TMT Bars
            {
                'title': 'URC Constructions Wins Bid for Veerannapalya Metro Station',
                'company': 'URC Constructions',
                'value': 850,
                'description': 'URC Constructions has won the bid for construction of Veerannapalya Metro Station.',
                'start_date': datetime.now() + timedelta(days=365),  # Q4 2025
                'end_date': datetime.now() + timedelta(days=365 + (36 * 30)),  # 36 months assumed
                'source': 'constructionworld.in',
                'source_url': 'https://www.constructionworld.in/transport-infrastructure/metro-rail-and-railways-infrastructure/urc-constructions-wins-bid-for-veerannapalya-metro-station/68599',
                'teams': ['TMT_BARS'],
                'steel_requirements': {
                    'primary': {'type': 'TMT Bars', 'quantity': 12000},
                    'secondary': {'type': 'HR Plates', 'quantity': 6000},
                    'total': 18000
                },
                'contacts': [{
                    'name': 'Dhinesh Kumar',
                    'role': 'AGM - Procurement',
                    'email': 'dhinesh.kumar@urcindia.com',
                    'phone': '+91 9032898833'
                }],
                'priority_score': 65,
                'final_priority_score': 65,
                'tags': ['Normal Priority'],
                'relationship_notes': 'JSW has previously supplied JSW Neosteel TMT bars for URC Construction\'s project Ramanujam IT Park'
            },
            # Highway project with TMT Bars
            {
                'title': 'DRA Infracon wins Rs 4,900 crore BOT Toll highway project in Assam',
                'company': 'DRA Infracon',
                'value': 4900,
                'description': 'DRA Infracon has secured a 121 km long BOT Toll highway project in Assam.',
                'start_date': datetime.now() + timedelta(days=365),  # Q4 2025
                'end_date': datetime.now() + timedelta(days=365 + (36 * 30)),  # 36 months assumed
                'source': 'economictimes.indiatimes.com',
                'source_url': 'https://infra.economictimes.indiatimes.com/news/roads-highways/dra-infracon-wins-rs-4900-crore-bot-toll-highway-project-in-assam/117976496',
                'teams': ['TMT_BARS'],
                'steel_requirements': {
                    'primary': {'type': 'TMT Bars', 'quantity': 10000},
                    'total': 10000
                },
                'contacts': [{
                    'name': 'Sushil Awasthi',
                    'role': 'GM-Procurement at DRA Infracon',
                    'email': 'sushilawasthi@gril.com',
                    'phone': '+91 77260 09528'
                }],
                'priority_score': 85,
                'final_priority_score': 85,
                'tags': ['High Priority']
            }
        ]

        success = email_handler.send_project_opportunities(test_projects)

        if success:
            return jsonify({
                'status': 'success',
                'message': 'Test emails sent successfully'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to send test emails'
            }), 500

    except Exception as e:
        logger.error(f"Error sending test emails: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/webhook/whatsapp', methods=['POST'])
def whatsapp_webhook():
    """Handle incoming WhatsApp messages from Interakt"""
    try:
        data = request.json
        logger.info(f"Received webhook: {data}")

        # Extract message details
        if data.get('type') == 'message' and data.get('payload'):
            payload = data['payload']
            phone_number = payload.get('from', {}).get('phone')
            message_text = payload.get('text', {}).get('body')

            if phone_number and message_text:
                # Handle the message
                whatsapp_handler.handle_incoming_message(
                    phone_number, message_text)
                return jsonify({'status': 'success'}), 200
            else:
                logger.error("Missing phone number or message text in webhook")
                return jsonify({'error': 'Invalid payload'}), 400
        else:
            logger.error("Invalid webhook type or missing payload")
            return jsonify({'error': 'Invalid webhook type'}), 400

    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
