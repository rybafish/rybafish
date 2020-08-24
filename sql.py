
hosts_info = '''select host, '' port, min(time) min_time, max(time) max_time from m_load_history_host
group by host

union

select host, to_nvarchar(port) port, min(time) min_time, max(time) max_time from m_load_history_service
group by host, port
order by host, port'''

hosts_info_experimental = '''select t.host, t.port, t.min_time, t.max_time, s.service_name from 
(select host, '' port, min(time) min_time, max(time) max_time from m_load_history_host
group by host

union

select host, to_nvarchar(port) port, min(time) min_time, max(time) max_time from m_load_history_service
group by host, port
) t
left join m_services s
on t.host = s.host and t.port = to_nvarchar(s.port)
order by host, port'''

kpis_info = '''select
	display_hierarchy,
	view_name,
	column_name,
	display_y_scale,
	display_name,
	description,

	sample_unit,
	display_unit,
	
	display_line_color,
	display_line_style
from m_load_history_info order by display_hierarchy'''