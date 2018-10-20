ALTER TABLE archetype ADD COLUMN guidance TEXT;
UPDATE archetype SET guidance='';
UPDATE archetype SET guidance='Kill the opponent quickly by attacking with creatures.' WHERE name='Aggro';
UPDATE archetype SET guidance='Execute a specific interaction which immediately wins the game or generates insurmountable advantage.' WHERE name='Combo';
UPDATE archetype SET guidance='Answer threats while generating card advantage.' WHERE name='Control';
UPDATE archetype SET guidance='Accelerate mana to play big threats before they can be answered.' WHERE name='Ramp';
UPDATE archetype SET guidance='Do not add decks to this archetype' WHERE name='Unclassified';