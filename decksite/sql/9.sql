-- Allow a tree of nested archetypes in a way that is easy to query and manipulate.
-- See https://www.slideshare.net/billkarwin/sql-antipatterns-strike-back/68-Naive_Trees_Solution_3_Closure

CREATE TABLE IF NOT EXISTS archetype_closure (
    ancestor INT,
    descendant INT,
    depth INT,
    PRIMARY KEY (ancestor, descendant),
    FOREIGN KEY(ancestor) REFERENCES archetype(id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY(descendant) REFERENCES archetype(id) ON UPDATE CASCADE ON DELETE CASCADE
);
