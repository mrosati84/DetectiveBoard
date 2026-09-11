"""Shared SQL column lists for cards and notes.

Keeping these in one place avoids drift between SELECT, INSERT and RETURNING
clauses across service modules.
"""

CARD_FIELDS = (
    "id, title, description, image_path, pos_x, pos_y, pin_position, inactive, color"
)
CARD_INSERT_COLUMNS = "board_id, title, description, image_path, pos_x, pos_y, pin_position, inactive, color"
NOTE_FIELDS = "id, content, pos_x, pos_y"
