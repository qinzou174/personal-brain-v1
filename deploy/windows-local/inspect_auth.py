import sqlalchemy as sa

eng = sa.create_engine(open(r"E:\Personal-Brain-V1-local\secrets\db-dsn").read().strip())
with eng.connect() as c:
    row = c.execute(sa.text(
        "select scopes, allowed_tools from clients where id='91914bb7-461b-481d-8993-8970251e0cc7'")).one()
    print("scopes:", row[0])
    print("allowed_tools:", row[1])
    print("grants:")
    for r in c.execute(sa.text(
            "select effect, scope_pattern, tool_pattern from permission_grants "
            "where client_id='91914bb7-461b-481d-8993-8970251e0cc7' order by tool_pattern")):
        print("  ", tuple(r))
