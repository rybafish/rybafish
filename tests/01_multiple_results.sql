-- simple unassigned
do begin
    select * from dummy;
    select 'b' b from dummy;
    select 3 c from dummy;
    select * from m_load_history_host;
end;

-- most possible simple one table output procedure
drop procedure test01_regular;

create procedure test01_regular(out outtab1 table(abc nvarchar(5), def nvarchar(7)))
as
begin

   outtab1 = select 'abc' abc, 'def' def from dummy;

end;

call test01_regular(?);

-- one scalar output procedure
drop procedure test02_scalar;

create procedure test02_scalar(out j integer)
as
begin

   j := 888;

end;

call test02_scalar(?);

-- one scalar input, one output procedure

drop procedure test03_scalar;

create procedure test03_scalar(in i integer, out j integer, out k nvarchar(5))
as
begin

   j := i*10 + 8;
   k := to_varchar(to_int(j/2));

end;

call test03_scalar(88, ?, ?);

-- two tables outputs, actual table types

drop procedure test04_multiple1;

drop type outtab1;

create type outtab1 as table (
    ab nvarchar(5),
    cd nvarchar(5)
);

drop type outtab2;
create type outtab2 as table (
    ef nvarchar(5),
    gh nvarchar(5)
);

create procedure test04_multiple1(out a outtab1, out b outtab2)

as
begin

   a = select 'abc' ab, 'def' cd from dummy;
   b = select 'abc' ef, 'def' gh from dummy;

end;

call test04_multiple1(?, ?);

-- two table outputs, inline
drop procedure test04_multiple2;
create procedure test04_multiple2(out outtab1 table(ab nvarchar(5), cd nvarchar(7)), out outtab2 table(ef nvarchar(5), gh nvarchar(7)))
as
begin

   outtab1 = select 'abc' ab, 'def' cd from dummy;
   outtab2 = select 'abc' ef, 'def' gh from dummy;

end;

call test04_multiple2(?, ?);


-- table output + 1 scalar output
drop procedure test04_combo1;
create procedure test04_combo1(in c integer, out d integer)
as
begin

    select * from dummy;

    d:= 11;

end;

call test04_combo1(1, ?);

-- table output + 2 scalar outputs: should drop an exception
drop procedure test04_combo2;
create procedure test04_combo2(in c integer, out d integer, e varchar(7))
as
begin

    select 1, 2, 3 from dummy;

    d:= 11;
    e:= '11';

end;

call test04_combo2(1, ?, ?);


-- make sure lobs scalar work
select top 1 host || ':' || port host from m_load_history_service where port like '%03';
call sys.management_console_proc('profiler clear', '...', ?);
