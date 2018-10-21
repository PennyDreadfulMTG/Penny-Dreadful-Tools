ALTER TABLE archetype ADD COLUMN description TEXT;
UPDATE archetype SET description='';
UPDATE archetype SET description='Kill the opponent quickly by attacking with creatures.' WHERE name='Aggro';
UPDATE archetype SET description='Execute a specific interaction which immediately wins the game or generates insurmountable advantage.' WHERE name='Combo';
UPDATE archetype SET description='Answer threats while generating card advantage.' WHERE name='Control';
UPDATE archetype SET description='Accelerate mana to play big threats before they can be answered.' WHERE name='Ramp';
UPDATE archetype SET description='Do not add decks to this archetype' WHERE name='Unclassified';