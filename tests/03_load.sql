do begin 
    declare s, i integer;

    for i in 1..400 * 10 do
        select sum(version_id) into s from _sys_repo.active_object;
    end for;

    select :s from dummy;
end;