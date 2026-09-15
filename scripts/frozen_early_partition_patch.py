import ast


def patch(source):
    old="if depth==0 and req['max_tokens']>=6000 and available<4096 else None"
    assert source.count(old)==1
    source=source.replace(old,"if depth==0 and req['max_tokens']>available and available<4096 else None")
    ast.parse(source)
    return source
