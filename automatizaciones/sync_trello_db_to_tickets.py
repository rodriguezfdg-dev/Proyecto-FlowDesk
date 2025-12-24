# -*- coding: utf-8 -*-
import os
import sys
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, joinedload
from datetime import datetime, timezone

# --- Path Setup ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# --- DB Setup ---
try:
    from dotenv import load_dotenv
    dotenv_path = os.path.join(os.path.dirname(__file__), '.env.local')
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
except ImportError:
    print("python-dotenv not found, relying on system environment variables.")

from backend import models

DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "root")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_NAME = os.getenv("DB_NAME", "innovaweb")

DATABASE_URL = f"mysql+mysqlconnector://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_trello_creation_date(trello_card_id):
    """Converts the timestamp part of a Trello card ID into a datetime object."""
    try:
        timestamp = int(trello_card_id[0:8], 16)
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)

def sync_trello_to_tickets():
    """
    Reads Trello card data from the local DB mirror and creates new tickets
    in the application's Cards table if they don't already exist.
    """
    db = SessionLocal()
    print(f"--- Running Trello DB Sync at {datetime.now(timezone.utc)} ---")
    
    try:
        # 1. Get all active boards marked for updating
        active_boards = db.query(models.Board).options(joinedload(models.Board.lists)).filter_by(UpdateC=True, Closed=False).all()
        if not active_boards:
            print("No active boards found for updating. Exiting.")
            return

        print(f"Found {len(active_boards)} boards to process.")

        new_tickets_created_total = 0
        for board in active_boards:
            print(f"\nProcessing board: '{board.Name}' (ID: {board.ID}) for customer '{board.Customer}'")
            
            # 2. Get the raw Trello JSON data for the board using the correct column 'Code'
            trello_data = db.query(models.TrelloBoardData).filter_by(Code=board.ID).first()
            if not trello_data or not trello_data.Data:
                print(f" > No Trello data found for board with Code/ID {board.ID}. Skipping.")
                continue

            try:
                trello_cards_json = json.loads(trello_data.Data)
            except json.JSONDecodeError:
                print(f" > Invalid JSON data for board Code/ID {board.ID}. Skipping.")
                continue

            # Create a quick lookup for Trello list IDs to our app's status
            list_to_status_map = {lst.ID: (lst.OpenStatus, lst.State) for lst in board.lists}
            
            new_tickets_on_board = 0
            for trello_card in trello_cards_json:
                card_url = trello_card.get("shortUrl")
                if not card_url:
                    continue

                # 3. Check if a ticket for this Trello card already exists
                existing_ticket = db.query(models.Card).filter(models.Card.LinkTrello == card_url).first()
                if existing_ticket:
                    continue # Skip if ticket already exists

                # 4. If it doesn't exist, create it
                trello_list_id = trello_card.get("idList")
                if trello_list_id not in list_to_status_map:
                    continue # Skip if the card's list isn't mapped to a status in our system
                    
                app_status_id, app_status_name = list_to_status_map[trello_list_id]

                print(f"  > Creating new ticket for Trello card: '{trello_card.get('name')}'")
                print(f"  > DEBUG: Value of board.Assigned for this board: '{board.Assigned}'")

                new_ticket = models.Card(
                    Name=trello_card.get("name", "Sin Título"),
                    Comment=trello_card.get("desc", ""),
                    Priority="Baja", # Default priority
                    State=app_status_name,
                    CardStatus=app_status_id,
                    CustCode=board.Customer,
                    LinkTrello=card_url,
                    TrelloId=trello_card.get("idShort"),
                    date_column=get_trello_creation_date(trello_card.get("id")),
                    state_last_changed_date=datetime.now(timezone.utc),
                    Department=board.Department,
                    assign=board.Assigned or "updcards",
                )

                customer = db.query(models.Cliente).filter(models.Cliente.code == board.Customer).first()
                if customer:
                    new_ticket.nombre_cliente = customer.razon_social

                db.add(new_ticket)
                new_tickets_on_board += 1

            if new_tickets_on_board > 0:
                print(f" > Found {new_tickets_on_board} new tickets to create for this board.")
                new_tickets_created_total += new_tickets_on_board

        if new_tickets_created_total > 0:
            db.commit()
            print(f"\nSuccessfully created a total of {new_tickets_created_total} new tickets.")
        else:
            print("\nNo new tickets to create across all boards.")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        db.rollback()
    finally:
        print("--- Trello DB Sync finished ---")
        db.close()


if __name__ == "__main__":
    sync_trello_to_tickets()