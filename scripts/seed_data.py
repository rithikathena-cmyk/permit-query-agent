"""Populate permit_system with realistic sample data.

Run:  python -m scripts.seed_data

Idempotent: clears existing rows (child -> parent order) before inserting.
Uses a fixed random seed so re-runs produce the same dataset.
"""
import random
from datetime import date, timedelta

from sqlalchemy import delete

from app.database.connection import SessionLocal
from app.models import City, Officer, Permit, PermitStatus, PermitType

random.seed(42)

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------
PERMIT_TYPES = [
    ("Electrical", "Electrical installations"),
    ("Building", "Residential & commercial buildings"),
    ("Mechanical", "Mechanical systems"),
    ("Plumbing", "Water & drainage systems"),
    ("Roofing", "Roof construction"),
    ("Demolition", "Building demolition"),
    ("HVAC", "Heating and cooling systems"),
    ("Fire Safety", "Fire protection systems"),
]

STATUSES = [
    "Pending",
    "Approved",
    "Rejected",
    "Under Review",
    "Inspection Scheduled",
]

# Weighted distributions (percentages) so records are not evenly spread.
TYPE_WEIGHTS = {
    "Building": 30,
    "Electrical": 20,
    "Plumbing": 15,
    "Mechanical": 10,
    "Roofing": 10,
    "HVAC": 5,
    "Fire Safety": 5,
    "Demolition": 5,
}

STATUS_WEIGHTS = {
    "Approved": 40,
    "Pending": 30,
    "Under Review": 15,
    "Inspection Scheduled": 10,
    "Rejected": 5,
}

CITIES = [
    ("Austin", "Travis", "Texas"),
    ("Dallas", "Dallas", "Texas"),
    ("Houston", "Harris", "Texas"),
    ("San Antonio", "Bexar", "Texas"),
    ("Fort Worth", "Tarrant", "Texas"),
    ("El Paso", "El Paso", "Texas"),
    ("Arlington", "Tarrant", "Texas"),
    ("Corpus Christi", "Nueces", "Texas"),
    ("Plano", "Collin", "Texas"),
    ("Laredo", "Webb", "Texas"),
    ("Phoenix", "Maricopa", "Arizona"),
    ("Tucson", "Pima", "Arizona"),
    ("Denver", "Denver", "Colorado"),
    ("Colorado Springs", "El Paso", "Colorado"),
    ("Los Angeles", "Los Angeles", "California"),
    ("San Diego", "San Diego", "California"),
    ("Sacramento", "Sacramento", "California"),
    ("Las Vegas", "Clark", "Nevada"),
    ("Albuquerque", "Bernalillo", "New Mexico"),
    ("Oklahoma City", "Oklahoma", "Oklahoma"),
]

FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael",
    "Linda", "David", "Elizabeth", "William", "Barbara", "Richard", "Susan",
    "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen", "Daniel",
    "Nancy", "Matthew", "Lisa", "Anthony", "Betty", "Mark", "Sandra",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
]

DEPARTMENTS = [
    "Electrical",
    "Building",
    "Mechanical",
    "Plumbing",
    "Inspection",
]

def clear_tables(session):
    """Remove existing rows, children first to respect FK constraints."""
    session.execute(delete(Permit))
    session.execute(delete(PermitType))
    session.execute(delete(PermitStatus))
    session.execute(delete(City))
    session.execute(delete(Officer))
    session.commit()


def seed_reference(session):
    permit_types = [PermitType(name=n, description=d) for n, d in PERMIT_TYPES]
    statuses = [PermitStatus(status=s) for s in STATUSES]
    cities = [
        City(city_name=c, county=co, state=st) for c, co, st in CITIES
    ]

    officers = []
    used = set()
    while len(officers) < 25:
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        name = f"{first} {last}"
        if name in used:
            continue
        used.add(name)
        email = f"{first.lower()}.{last.lower()}@permits.gov"
        officers.append(
            Officer(
                name=name,
                email=email,
                department=random.choice(DEPARTMENTS),
            )
        )

    session.add_all(permit_types + statuses + cities + officers)
    session.commit()
    return permit_types, statuses, cities, officers


def seed_permits(session, permit_types, statuses, cities, officers):
    num_permits = 1000
    today = date(2026, 7, 22)
    start = date(2025, 1, 1)  # submitted dates range from 2025-01-01 to today
    span_days = (today - start).days

    # Weight lists aligned to the ordering of the model objects.
    type_weights = [TYPE_WEIGHTS[t.name] for t in permit_types]
    status_weights = [STATUS_WEIGHTS[s.status] for s in statuses]

    permits = []
    for i in range(1, num_permits + 1):
        ptype = random.choices(permit_types, weights=type_weights, k=1)[0]
        status = random.choices(statuses, weights=status_weights, k=1)[0]
        city = random.choice(cities)
        officer = random.choice(officers)

        submitted = start + timedelta(days=random.randint(0, span_days))

        # approved_date only makes sense for Approved permits
        approved = None
        if status.status == "Approved":
            approved = submitted + timedelta(days=random.randint(5, 60))
            if approved > today:
                approved = today

        applicant = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        cost = round(random.uniform(500, 150_000), 2)

        permits.append(
            Permit(
                application_number=f"PERM-2026-{i:06d}",
                applicant_name=applicant,
                submitted_date=submitted,
                approved_date=approved,
                estimated_cost=cost,
                permit_type=ptype,
                status=status,
                city=city,
                officer=officer,
            )
        )

    session.add_all(permits)
    session.commit()
    return num_permits


def main():
    session = SessionLocal()
    try:
        clear_tables(session)
        permit_types, statuses, cities, officers = seed_reference(session)
        num_permits = seed_permits(
            session, permit_types, statuses, cities, officers
        )
        print("Seed complete:")
        print(f"  permit_types    : {len(permit_types)}")
        print(f"  permit_statuses : {len(statuses)}")
        print(f"  cities          : {len(cities)}")
        print(f"  officers        : {len(officers)}")
        print(f"  permits         : {num_permits}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
