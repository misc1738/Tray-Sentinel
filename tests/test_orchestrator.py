import asyncio

from services.orchestrator import SmartGridOrchestrator


def test_orchestrator_basic():
    orchestrator = SmartGridOrchestrator()
    # create simple synthetic sensor readings
    readings = [
        {"device_id": "FEEDER-F12", "sensor_type": "voltage", "value": 218.5, "quality": 0.98},
        {"device_id": "FEEDER-F12", "sensor_type": "voltage", "value": 221.2, "quality": 0.99},
    ]

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    res = loop.run_until_complete(orchestrator.process_sensor_data_stream(readings))
    assert res.get('success') is True
    assert 'system_status' in res
    assert 'anomalies' in res
