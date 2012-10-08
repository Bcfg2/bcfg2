{% load bcfg2_tags %}
<div class='interaction_history_widget'>
  <table cellpadding="3">
  <tr id='table_list_header' class='listview'>
    <td class='left_column'>Timestamp</td>
    {% if not client %}
    <td class='right_column_wide'>Client</td>
    {% endif %}
    <td class='right_column' style='width:75px'>State</td>
    <td class='right_column_narrow'>Good</td>
    <td class='right_column_narrow'>Bad</td>
    <td class='right_column_narrow'>Modified</td>
    <td class='right_column_narrow'>Extra</td>
    <td class='right_column_wide'>Server</td>
  </tr>
  {% for entry in entry_list %}
  <tr class='{% cycle listview,listview_alt %}'>
    <td class='left_column'><a href='{% url reports_client_detail_pk hostname=entry.client.name, pk=entry.id %}'>{{ entry.timestamp|date:"Y-m-d\&\n\b\s\p\;H:i"|safe }}</a></td>
    {% if not client %}
    <td class='right_column_wide'><a href='{% add_url_filter hostname=entry.client.name %}'>{{ entry.client.name }}</a></td>
    {% endif %}
    <td class='right_column' style='width:75px'><a href='{% add_url_filter state=entry.state %}'
        class='{{entry|determine_client_state}}'>{{ entry.state }}</a></td>
    <td class='right_column_narrow'>{{ entry.good_count }}</td>
    <td class='right_column_narrow'>{{ entry.bad_count }}</td>
    <td class='right_column_narrow'>{{ entry.modified_count }}</td>
    <td class='right_column_narrow'>{{ entry.extra_count }}</td>
    <td class='right_column_wide'>
       {% if entry.server %}
         <a href='{% add_url_filter server=entry.server %}'>{{ entry.server }}</a>
       {% else %}
         &nbsp;
       {% endif %}
    </td>
  </tr>
  {% endfor %}
  </table>
</div>
