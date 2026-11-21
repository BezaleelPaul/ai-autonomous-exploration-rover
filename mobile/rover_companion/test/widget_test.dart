import 'package:flutter_test/flutter_test.dart';
import 'package:rover_companion/main.dart';

void main() {
  testWidgets('RoverCompanionApp smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const RoverCompanionApp());
    expect(find.text('ROVERLINK'), findsOneWidget);
    expect(find.text('Drive Pad'), findsOneWidget);
    expect(find.text('Pairing'), findsOneWidget);
    expect(find.text('Pinout Guide'), findsOneWidget);
  });
}
