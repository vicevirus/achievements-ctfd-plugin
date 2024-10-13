from flask import Blueprint, render_template, current_app
from CTFd.utils.decorators import authed_only
from CTFd.models import Awards, Users, Solves, Challenges, Teams, db
from sqlalchemy.sql import func
from CTFd.plugins import register_plugin_assets_directory
from pathlib import Path
from CTFd.utils.plugins import override_template
from CTFd.utils import config

achievements = Blueprint('achievements', __name__, template_folder='templates')

@achievements.route("/achievements", methods=["GET"])
@authed_only
@current_app.cache.cached(timeout=60, key_prefix="achievements_listing")
def listing():
    
    if config.is_scoreboard_frozen():
        return render_template("scoreboard_frozen.html")
    
    # Subquery to find hidden teams and exclude them
    hidden_teams_subquery = db.session.query(Teams.id).filter(Teams.hidden == True).subquery()

    # Get the top 3 teams per category, excluding hidden teams
    subquery = (
        db.session.query(
            Solves.team_id,
            Challenges.category,
            func.count(Solves.id).label("solves_count"),
            func.row_number().over(
                partition_by=Challenges.category,
                order_by=func.count(Solves.id).desc()
            ).label("rank")
        )
        .join(Challenges, Solves.challenge_id == Challenges.id)
        .filter(~Solves.team_id.in_(hidden_teams_subquery))
        .group_by(Solves.team_id, Challenges.category)
        .subquery()
    )

    solves_per_team_category = (
        db.session.query(
            subquery.c.team_id,
            subquery.c.category,
            subquery.c.solves_count
        )
        .filter(subquery.c.rank <= 3)
        .all()
    )

    # Fetch relevant achievements, excluding hidden teams
    first_first_blood = (
        db.session.query(Solves.team_id)
        .filter(~Solves.team_id.in_(hidden_teams_subquery))  # Exclude hidden teams
        .order_by(Solves.date.asc())
        .first()
    )

    most_first_bloods = (
        db.session.query(Solves.team_id, func.count(Solves.id).label("first_bloods_count"))
        .filter(Solves.id.in_(
            db.session.query(func.min(Solves.id))
            .group_by(Solves.challenge_id)
        ))
        .filter(~Solves.team_id.in_(hidden_teams_subquery))  # Exclude hidden teams
        .group_by(Solves.team_id)
        .order_by(func.count(Solves.id).desc())
        .first()
    )

    lone_wolf = (
        db.session.query(
            Users.id, 
            Users.name, 
            func.count(Solves.id).label("solves_count"),
            func.min(Solves.date).label("first_solve_time")
        )
        .join(Solves, Solves.user_id == Users.id)
        .filter(~Users.team_id.in_(hidden_teams_subquery))  # Exclude hidden teams
        .group_by(Users.id, Users.name)
        .order_by(func.count(Solves.id).desc(), func.min(Solves.date).asc())
        .first()
    )

    collaborative_genius = (
        db.session.query(
            Teams.id.label("team_id"), 
            Teams.name.label("team_name"),
            (func.count(Solves.id) / func.count(Users.id)).label("avg_solves"),
            func.min(Solves.date).label("first_solve_time")
        )
        .join(Users, Users.team_id == Teams.id)
        .join(Solves, Solves.user_id == Users.id)
        .filter(Teams.hidden == False)  # Exclude hidden teams
        .group_by(Teams.id, Teams.name)
        .order_by(
            (func.count(Solves.id) / func.count(Users.id)).desc(),
            func.min(Solves.date).asc()
        )
        .first()
    )

    flag_conqueror_team = (
        db.session.query(
            Solves.team_id,
            func.count(Solves.id).label("solved_count"),
            func.min(Solves.date).label("first_solve_time")
        )
        .filter(~Solves.team_id.in_(hidden_teams_subquery))  # Exclude hidden teams
        .group_by(Solves.team_id)
        .order_by(
            func.count(Solves.id).desc(),
            func.min(Solves.date).asc()
        )
        .first()
    )

    # Initialize the category_gods dictionary with all possible achievements
    achievement_titles = {
        'web': {
            'title': '🕸️ The Gentle Web Expert',
            'description': 'You navigate the web like an artist—smooth and elegant. (Most Web Solves) 🌸'
        },
        'reverse engineering': {
            'title': '🔍 Enigmatic Engineer',
            'description': 'You reverse code with grace, unraveling mysteries with every step. (Most RE Solves) 🧚‍♀️'
        },
        're': {
            'title': '🔍 Enigmatic Engineer',
            'description': 'You reverse code with grace, unraveling mysteries with every step. (Most RE Solves) 🧚‍♀️'
        },
        'pwn': {
            'title': '💥 The Empowered Pwner',
            'description': 'You take on challenges with strength and confidence. (Most PWN Solves) ✨'
        },
        'crypto': {
            'title': '🔐 Elegant Cryptographer',
            'description': 'You decrypt secrets with poise, like a true international solver. (Most Crypto Solves) 💖'
        },
        'forensics': {
            'title': '🕵️‍♀️ Forensics Virtuoso',
            'description': 'Your investigative skills are second to none. (Most Forensics Solves) 🌷'
        },
        'misc': {
            'title': '🤹‍♀️ Jack of All Trades',
            'description': 'You gracefully handle any challenge thrown your way. (Most Miscellaneous Solves) 🎀'
        },
        'blockchain': {
            'title': '🔗 Blockchain Maven',
            'description': 'You’re the go-to solver when it comes to distributed ledgers. (Most Blockchain Solves) 💎'
        },
        'first_first_blood': {
            'title': '🥇 Graceful Trendsetter',
            'description': 'You’re the first to shine, solving challenges with beauty and speed. (First Solve of All Challenges) 🌟'
        },
        'double_blood': {
            'title': '🩸 Fierce Competitor',
            'description': 'You keep winning first blood, showing your passion for success. (Most First Bloods) 💪'
        },
        'lone_wolf': {
            'title': '🐺 The Fiercely Independent',
            'description': 'You accomplish great things all on your own. (Most Individual Solves) 🌸'
        },
        'master_of_disguise': {
            'title': '🎭 Master of Many Talents',
            'description': 'You seamlessly blend across categories, handling every challenge. (Solved Every Category) 🦋'
        },
        'collaborative_genius': {
            'title': '🧠 Collaborative Genius',
            'description': 'Your teamwork is unparalleled, solving challenges together. (Best Team Collaboration) 💕'
        },
        'flag_conqueror': {
            'title': '🏆 Ultimate Flag Conqueror',
            'description': 'You claim the most flags, a champion in every way. (Most Total Solves) 🌺'
        }
    }

    category_gods = {
        achievement_titles[title]['title']: {
            'teams': [],
            'max_solves': 0,
            'description': achievement_titles[title]['description']
        }
        for title in achievement_titles
    }

    # Fetch team names for achievements in bulk
    team_ids = set()
    team_achievements = {}

    if first_first_blood:
        team_ids.add(first_first_blood.team_id)
    if most_first_bloods:
        team_ids.add(most_first_bloods.team_id)
    if flag_conqueror_team:
        team_ids.add(flag_conqueror_team.team_id)
    
    for team_id, _, _ in solves_per_team_category:
        team_ids.add(team_id)

    team_names = {
        team.id: team.name
        for team in db.session.query(Teams.id, Teams.name).filter(Teams.id.in_(team_ids)).all()
    }

    # Calculate total achievements for each team
    for team_id in team_ids:
        team_achievements[team_id] = 0

    for team_id, category, solves_count in solves_per_team_category:
        category_lower = category.lower()
        title_info = achievement_titles.get(category_lower) 

        if title_info:
            title = title_info['title']
            if solves_count > category_gods[title]['max_solves']:
                category_gods[title]['max_solves'] = solves_count
                category_gods[title]['teams'] = [{
                    'name': team_names[team_id],
                    'id': team_id,
                    'type': 'team'
                }]
            elif solves_count == category_gods[title]['max_solves']:
                category_gods[title]['teams'].append({
                    'name': team_names[team_id],
                    'id': team_id,
                    'type': 'team'
                })
            
            # Increment team's achievements count
            team_achievements[team_id] += 1

    # Add the first first blood achievement
    if first_first_blood:
        title = achievement_titles['first_first_blood']['title']
        category_gods[title]['teams'] = [{
            'name': team_names[first_first_blood.team_id],
            'id': first_first_blood.team_id,
            'type': 'team'
        }]
        team_achievements[first_first_blood.team_id] += 1

    # Add the Double Blood achievement for the team with the most first bloods
    if most_first_bloods:
        title = achievement_titles['double_blood']['title']
        category_gods[title]['teams'] = [{
            'name': team_names[most_first_bloods.team_id],
            'id': most_first_bloods.team_id,
            'type': 'team'
        }]
        category_gods[title]['max_solves'] = most_first_bloods.first_bloods_count
        team_achievements[most_first_bloods.team_id] += 1

    # Add the Lone Wolf achievement
    if lone_wolf:
        title = achievement_titles['lone_wolf']['title']
        category_gods[title]['teams'] = [{
            'name': lone_wolf.name,
            'id': lone_wolf.id,
            'type': 'user'
        }]
        category_gods[title]['max_solves'] = lone_wolf.solves_count

    # Add the Collaborative Genius achievement
    if collaborative_genius:
        title = achievement_titles['collaborative_genius']['title']
        category_gods[title]['teams'] = [{
            'name': collaborative_genius.team_name,
            'id': collaborative_genius.team_id,
            'type': 'team'
        }]
        category_gods[title]['max_solves'] = collaborative_genius.avg_solves

    # Add the Flag Conqueror achievement
    if flag_conqueror_team:
        title = achievement_titles['flag_conqueror']['title']
        category_gods[title]['teams'] = [{
            'name': team_names[flag_conqueror_team.team_id],
            'id': flag_conqueror_team.team_id,
            'type': 'team'
        }]
        category_gods[title]['max_solves'] = flag_conqueror_team.solved_count
        team_achievements[flag_conqueror_team.team_id] += 1

    # Master of Disguise Achievement with Limited Winners
    max_winners = 3  # Limit to the first 3 teams that meet the criteria
    total_categories = db.session.query(Challenges.category).distinct().count()
    team_categories = {}
    for team_id, category, _ in solves_per_team_category:
        if team_id not in team_categories:
            team_categories[team_id] = set()
        team_categories[team_id].add(category)

    master_of_disguise_teams = sorted(
        [
            (team_id, len(categories)) for team_id, categories in team_categories.items()
            if len(categories) >= total_categories
        ],
        key=lambda x: x[1], reverse=True
    )[:max_winners]

    if master_of_disguise_teams:
        title = achievement_titles['master_of_disguise']['title']
        for team_id, _ in master_of_disguise_teams:
            team_name = team_names[team_id]
            category_gods[title]['teams'].append({
                'name': team_name,
                'id': team_id,
                'type': 'team'
            })
            team_achievements[team_id] += 1

    # Determine the Dominator team
    dominator_team_name = None
    if team_achievements:
        dominator_team_id = max(team_achievements, key=team_achievements.get)
        dominator_team_name = team_names[dominator_team_id]

    return render_template(
        "achievements.html", 
        category_gods=category_gods,
        dominator_team_name=dominator_team_name
    )


def load(app):
    # Register the achievements blueprint
    app.register_blueprint(achievements)
    
    # Register plugin assets directory if any (e.g., for static files or templates)
    register_plugin_assets_directory(app, base_path="/plugins/achievements/templates/")
    
    dir_path = Path(__file__).parent.resolve()
    template_path = dir_path / 'templates' / 'components' / 'navbar.html'
    
    # Debug: Check if the template path exists
    if not template_path.exists():
        print(f"Template path {template_path} does not exist")
    else:
        print(f"Overriding template with {template_path}")
        override_template('navbar.html', open(template_path).read())
