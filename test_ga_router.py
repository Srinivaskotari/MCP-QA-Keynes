from ga_router import route_ga_query

queries = [

    "show ga sessions by date",

    "show monthly users",

    "show sessions from 2026-05-01 to 2026-05-27"

]

for q in queries:

    print(q)

    print(route_ga_query(q))

    print("-" * 50)
