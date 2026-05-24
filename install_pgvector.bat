@echo off
copy "C:\Users\28744\AppData\Local\Temp\pgvector-src\pgvector-0.8.2\vector.dll" "C:\Program Files\PostgreSQL\17\lib\vector.dll"
copy "C:\Users\28744\AppData\Local\Temp\pgvector-src\pgvector-0.8.2\vector.control" "C:\Program Files\PostgreSQL\17\share\extension\vector.control"
copy "C:\Users\28744\AppData\Local\Temp\pgvector-src\pgvector-0.8.2\sql\vector--0.8.2.sql" "C:\Program Files\PostgreSQL\17\share\extension\vector--0.8.2.sql"
copy "C:\Users\28744\AppData\Local\Temp\pgvector-src\pgvector-0.8.2\sql\vector--0.8.1--0.8.2.sql" "C:\Program Files\PostgreSQL\17\share\extension\vector--0.8.1--0.8.2.sql"
echo Installation complete!
pause
