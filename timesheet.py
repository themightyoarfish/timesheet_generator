#!/usr/bin/env python3
# Timesheet generation script for Hiwis.

###
### Use following section to set your personal default values!
###
default_name = 'Diederichsen, Rasmus'
default_unit_of_organisation = "FB Mathematik/Informatik, Institut für Informatik"
default_hours = 25
default_days_of_week = [0, 1, 2, 3, 4]
default_start_hour = 8
default_end_hour = 20
default_max_hours = 6
default_output_file_name = 'timesheet'
default_state = 'NI'

# place here so the b64 literal can come at eof
logo = None
tex_pieces = None
entry_template = None

# current-date relative defaults
import datetime
default_month = datetime.date.today().month
default_year = datetime.date.today().year
default_ldom = datetime.date.today().day - 1
###
###
###

# imports
import datetime
import argparse
import holidays
import calendar
import numpy as np
import random
import os
import base64

###
### HELPER FUNCTIONS
###

def format_timedelta(td):
    '''Format datetime.timedelta as "hh:mm".'''
    s = td.total_seconds()
    return "{:0>2d}:{:0>2d}".format(int(s // 3600), int((s % 3600) // 60))

def weighted_choice(choices):
    '''Select random choice from list of (option, weight) pairs according to the weights.'''
    choices = list(choices)
    total = sum(w for c, w in choices)
    r = random.uniform(0, total)
    upto = 0
    for c, w in choices:
        if upto + w >= r:
            return c, w
        upto += w
    return c, w


def create():
    ###
    ### DATA GENERATION
    ###

    # get public holidays and legth of the month
    public_holidays = holidays.DE(state='NI', years=year)
    days_in_month = calendar.monthrange(year, month)[1]

    # check which days are valid, i.e. are specified workdays and not holidays
    valid_days = []
    for day in range(1, min(days_in_month, ldom) + 1):
        date = datetime.date(year, month, day)
        if date not in public_holidays and date.weekday() in days_of_week:
            valid_days.append(day)

    # distribute hours over valid days. use exponential weights (after random shuffle) for days, so some days are used often and some are used rarely
    possible_days = valid_days
    random.shuffle(possible_days)
    weights = list(1 / np.arange(1, len(possible_days) + 1))

    # collector for sampled distribution
    # day => (start, end)
    collector = dict()

    # possible chunks over the day are from start to end in steps of half-hours
    chunk_starts = np.arange(work_start, work_end, 0.5)

    # distribute all hours
    h = hours
    while h > 0:
        if len(possible_days) == 0:
            raise RuntimeError("Could not work off all hours with given parameters!")
        # select day
        day, weight = weighted_choice(zip(possible_days, weights))
        # if day is already listed, extend working hours there either before or after
        if day in collector:
            start, end = collector[day]
            possible_extensions = []
            if start > work_start:
                possible_extensions.append('before')
            if end < (work_end - 0.5):
                possible_extensions.append('after')
            extension = random.choice(possible_extensions)
            if extension == 'before':
                start -= 0.5
            if extension == 'after':
                end += 0.5
            collector[day] = (start, end)
            if end - start == max_hours:
                possible_days.remove(day)
                weights.remove(weight)
        # if day not yet listed, select random starting chunk
        else:
            start = random.choice(chunk_starts)
            end = start + 0.5
            collector[day] = (start, end)
        # half and hour was distributed off
        h -= 0.5


    ###
    ### FORMATTING DATA
    ###

    # extract relevant data from work distribution
    # list entries are strings: (day, start_time, end_time, duration, recording_date)
    data = []
    day_fmt = "{}, {:02d}.{:02d}.{:4d}"
    for day in range(1, days_in_month + 1):
        date = datetime.date(year, month, day)
        if day in collector:
            print(date)
            s, e = collector[day]
            s_h = int(s)
            s_m = int((s % 1) * 60)
            e_h = int(e)
            e_m = int((e % 1) * 60)
            start = datetime.datetime.combine(date, datetime.time(s_h, s_m))
            end = datetime.datetime.combine(date, datetime.time(e_h, e_m))
            duration = end - start
            day_str = day_fmt.format(date.strftime("%A")[:3], date.day,
                    date.month, date.year)


            data.append((
                day_str,
                start.strftime("%H:%M"),
                end.strftime("%H:%M"),
                format_timedelta(duration),
                day_str,
                "",
            ))
        else:
            day_str = day_fmt.format(date.strftime("%A")[:3], date.day,
                    date.month, date.year)
            if date in public_holidays:
                day_str = "\\cellcolor{lightgray!50}" + day_str

            data.append((
                day_str,
                "",
                "",
                "",
                "",
                public_holidays[date] if date in public_holidays else ""
            ))

    # additional format strings
    header_date = "{} {}".format(date.strftime("%B"), year)
    total_hours_formatted = format_timedelta(datetime.timedelta(hours=hours))



    ### 
    ### BUILD
    ###

    # logo
    logo_binary = base64.decodebytes(logo)
    with open('logo.png', 'wb') as f:
        f.write(logo_binary)


    # write template to file and fill it with the data
    with open("{}.tex".format(filename), "w") as f:
        f.write(tex_pieces[0])
        f.write(name)
        f.write(tex_pieces[1])
        f.write(uoo)
        f.write(tex_pieces[2])
        f.write(header_date)
        f.write(tex_pieces[3])
        f.write(total_hours_formatted)
        f.write(tex_pieces[4])
        for entries in data:
            f.write(entry_template.format(*entries))
        f.write(entry_template.format(r"\multicolumn{1}{|l|}{\textbf{Summe}}",
            "", "", total_hours_formatted, "", ""))
        f.write(tex_pieces[5])

    # compile latex and remove additional files
    os.system("pdflatex {}.tex".format(filename))
    os.remove("{}.aux".format(filename))
    os.remove("{}.log".format(filename))
    os.remove("{}.tex".format(filename))
    os.remove("logo.png")

def init():
    ###
    ### PARSE ARGUMENTS
    ###

    # parse arguments
    parser = argparse.ArgumentParser(description='Generate University Timesheets.', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-n', help='name of the employee', default=default_name)
    parser.add_argument('-y', help='year (defaults to current)', type=int, default=default_year)
    parser.add_argument('-m', help='month (defaults to current)', type=int, default=default_month)
    parser.add_argument('-ldom', help='last day of the month that should be used (defaults to yesterday)', type=int, default=default_ldom)
    parser.add_argument('-dow', help='days of the week (monday = 0, tuesday = 1, ...)', type=int, nargs='*', default=default_days_of_week)
    parser.add_argument('-uoo', help='unit of organisation', default=default_unit_of_organisation)
    parser.add_argument('-hrs', help='hours', type=int, default=default_hours)
    parser.add_argument('-s', help='start time', type=int, default=default_start_hour)
    parser.add_argument('-e', help='end time', type=int, default=default_end_hour)
    parser.add_argument('-max', help='maximum hours for a day', type=int, default=default_max_hours)
    parser.add_argument('-o', help='output file name', default=default_output_file_name)
    parser.add_argument('-state', help='german state for public holiday considerations, from list: BW, BY, BE, BB, HB, HH, HE, MV, NI, NW, RP, SL, SN, ST, SH, TH', default=default_state)

    args = parser.parse_args()

    # get parsed arguments
    global name, uoo, year, month, days_of_week, hours, work_start, max_hours, work_end, filename, ldom
    name = args.n
    uoo = args.uoo
    year = args.y
    month = args.m
    days_of_week = args.dow
    hours = args.hrs
    work_start = args.s
    max_hours = args.max
    work_end = args.e
    filename = args.o
    ldom = args.ldom

    ###
    ### LATEX TEMPLATE
    ###

    global tex_pieces
    tex_pieces = [
    # begin

    r"""
    \documentclass[8pt]{scrartcl}
    \usepackage[a4paper, top=0cm, left=0cm, right=0cm, bottom=0cm]{geometry}
    \usepackage[utf8]{inputenc}

    \usepackage{graphicx}
    \usepackage{colortbl}
    \usepackage{xcolor}
    \renewcommand{\arraystretch}{1.2}
    \usepackage{booktabs, tabularx}

    \usepackage{array}
    \makeatletter
    \g@addto@macro{\endtabular}{\rowfont{}}% Clear row font
    \makeatother
    \newcommand{\rowfonttype}{}% Current row font
    \newcommand{\rowfont}[1]{% Set current row font
       \gdef\rowfonttype{#1}#1%
    }
    \newcolumntype{P}{>{\rowfonttype}p}


    \setlength\parindent{0pt}

    \begin{document}
    \thispagestyle{empty}
    \fontfamily{qhv}\selectfont

    \includegraphics[width=0.35\paperwidth]{logo.png}

    \vspace{0.2cm}


    \begin{addmargin}{2.2cm}
      
      \begin{tabular}{l c}
        \textbf{\large Erfassung der geleisteten Arbeitszeiten} & \\
      \end{tabular}
      
      \vspace{0.5cm}
      \begin{bfseries}
      \begin{tabular}{p{.4\linewidth} >{\centering\arraybackslash}p{.53\linewidth}}
        Name, Vorname der Hilfskraft: & """,
        
    # Name

    r"""
        \\ \cmidrule{2-2}
        Fachbereit/Organisationseinheit: & """,

    # Organisationseinheit

    r"""
        \\ \cmidrule{2-2}
        Monat/Jahr: & """,

    # Monat/Jahr

    r"""
        \\ \cmidrule{2-2}
        Monatsarbeitszeit laut Arbeitsvertrag: & """,

    # Arbeitszeit

    r"""
        \\ \cmidrule{2-2}
      \end{tabular}
      \end{bfseries}

      \vspace{0.5cm}

      \begin{tabularx}{.8\textwidth}{|>{\raggedleft}p{2.5cm}|p{1.2cm}|p{1.2cm}|p{1.2cm}|p{1.2cm}|>{\raggedleft}p{2.5cm}|X|}
        \hline
        Kalender-tag & Beginn (Uhrzeit) & Pause (Dauer) & Ende (Uhrzeit) & Dauer (Summe) & aufgezeichnet am: & Bemerkungen\\\hline
        &&&&&&\\\hline """,

    # data

    r"""
      \end{tabularx}
      
      \vspace{0.1cm}

      \vspace{1.5cm}

      $\rule{7.9cm}{0.1mm}$ ~~~ $\rule{7.9cm}{0.1mm}$

      \vspace{0.3cm}
      Datum, Unterschrift der Hilfskraft \hspace{3.65cm} Datum, Unterschrift der Leiterin / des Leiter der OE
      
      \hspace{9.5cm}alternativ: Vorgesetzte / Vorgesetzter

    \end{addmargin}

    \end{document}
    """
    ]
    
    global entry_template
    entry_template = "{}&{}&&{}&{}&{}&{}\\\\\\hline\n"

    ###
    ### UNIVERSITY LOGO
    ###

    global logo
    logo = b"""
    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"""


if __name__ == "__main__":
    init()
    create()

