import unittest
from unittest.mock import Mock, patch

from services.materials_service import MaterialsService
from services.neo4j_service import Neo4jService


class MaterialLearningTests(unittest.TestCase):
    def test_examples_are_read_from_completeknowledgebase(self):
        config = Mock()
        service = Neo4jService(config=config)
        with patch.object(service, "_run_query", return_value=[{"text": "Reference"}]) as run_query:
            self.assertEqual(service.get_existing_learning_materials("J.620100.005.02"), ["Reference"])

        self.assertEqual(run_query.call_args.kwargs["database"], "completeknowledgebase")
        self.assertEqual(run_query.call_args.args[1], {"kode": "J.620100.005.02"})

    def test_generation_prompt_uses_unit_references(self):
        neo4j_service = Mock()
        neo4j_service.get_existing_learning_materials.return_value = ["Reference lesson"]
        provider = Mock()
        provider.name = "test-provider"
        provider.chat.return_value = "TOPIC: Testing\n---\nMATERIAL:\nGenerated lesson"
        service = MaterialsService(mastery_service=Mock(), neo4j_service=neo4j_service)

        with patch("services.materials_service.get_llm_provider", return_value=provider):
            result = service.generate_learning_material("J.620100.005.02", "Web Application Development")

        prompt = provider.chat.call_args.args[0][0]["content"]
        self.assertIn("UNIT CODE: J.620100.005.02", prompt)
        self.assertIn("CORE COMPETENCY: Web Application Development", prompt)
        self.assertIn("Reference lesson", prompt)
        self.assertIn("Do not let them replace, narrow, or redirect", prompt)
        self.assertEqual(result["material"], provider.chat.return_value)
        self.assertEqual(result["provider"], "test-provider")

    def test_generation_requires_references(self):
        neo4j_service = Mock()
        neo4j_service.get_existing_learning_materials.return_value = []
        service = MaterialsService(mastery_service=Mock(), neo4j_service=neo4j_service)

        with self.assertRaisesRegex(ValueError, "No reference learning materials"):
            service.generate_learning_material("J.620100.005.02", "Web Application Development")


if __name__ == "__main__":
    unittest.main()