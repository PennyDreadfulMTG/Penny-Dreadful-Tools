-- Speed up /admin/archetypes
CREATE INDEX idx_rule_id_card_include_n ON rule_card(rule_id, card, include, n);
