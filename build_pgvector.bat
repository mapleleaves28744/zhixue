@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x64
set PATH=C:\Program Files\PostgreSQL\17\bin;%PATH%
set PGROOT=C:\Program Files\PostgreSQL\17
cd /d C:\Users\28744\AppData\Local\Temp\pgvector-src\pgvector-0.8.2
nmake /F Makefile.win install
