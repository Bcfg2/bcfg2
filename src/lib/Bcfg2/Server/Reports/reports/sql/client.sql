CREATE VIEW reports_current_interactions AS SELECT x.client_id AS client_id, reports_interaction.id AS interaction_id FROM (select client_id, MAX(timestamp) as timer FROM reports_interaction GROUP BY client_id) x, reports_interaction WHERE reports_interaction.client_id = x.client_id AND reports_interaction.timestamp = x.timer;

create index reports_interaction_client_id on reports_interaction (client_id);
create index reports_client_current_interaction_id on reports_client (current_interaction_id);
create index reports_performance_interaction_performance_id on reports_performance_interaction (performance_id);
create index reports_interaction_timestamp on reports_interaction (timestamp);
create index reports_performance_interation_interaction_id on reports_performance_interaction (interaction_id);
