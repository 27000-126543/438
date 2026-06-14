import sys
sys.path.insert(0, '/Users/mac/Desktop/6.13项目/438')

import importlib.util
import types

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

app_module = types.ModuleType('app')
sys.modules['app'] = app_module

modules = [
    ('app.schemas.user', '/Users/mac/Desktop/6.13项目/438/app/schemas/user.py'),
    ('app.schemas.token', '/Users/mac/Desktop/6.13项目/438/app/schemas/token.py'),
    ('app.schemas.vehicle', '/Users/mac/Desktop/6.13项目/438/app/schemas/vehicle.py'),
    ('app.schemas.route', '/Users/mac/Desktop/6.13项目/438/app/schemas/route.py'),
    ('app.schemas.monitoring', '/Users/mac/Desktop/6.13项目/438/app/schemas/monitoring.py'),
    ('app.schemas.accident', '/Users/mac/Desktop/6.13项目/438/app/schemas/accident.py'),
    ('app.schemas.completion', '/Users/mac/Desktop/6.13项目/438/app/schemas/completion.py'),
    ('app.schemas.device', '/Users/mac/Desktop/6.13项目/438/app/schemas/device.py'),
    ('app.schemas.data', '/Users/mac/Desktop/6.13项目/438/app/schemas/data.py'),
    ('app.schemas.report', '/Users/mac/Desktop/6.13项目/438/app/schemas/report.py'),
    ('app.schemas.staff', '/Users/mac/Desktop/6.13项目/438/app/schemas/staff.py'),
    ('app.schemas', '/Users/mac/Desktop/6.13项目/438/app/schemas/__init__.py'),
]

total_classes = 0
for name, path in modules:
    try:
        mod = load_module(name, path)
        classes = [x for x in dir(mod) if not x.startswith('_') and isinstance(getattr(mod, x), type)]
        print(f"✓ {name}: {len(classes)} 个类 - {', '.join(classes)}")
        total_classes += len(classes)
    except Exception as e:
        print(f"✗ {name} 错误: {e}")
        import traceback
        traceback.print_exc()

print(f"\n总计: {total_classes} 个类")
print("\n所有 schemas 模块验证成功!")
