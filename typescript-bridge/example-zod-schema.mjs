import { z } from "zod";
import { zodToJsonSchema } from "zod-to-json-schema";

const ClassifyRequestInput = z.object({
  request: z.string().describe("Business request to classify"),
});

const schema = zodToJsonSchema(ClassifyRequestInput, {
  name: "ClassifyRequestInput",
  target: "jsonSchema7",
});

console.log(JSON.stringify(schema.definitions.ClassifyRequestInput, null, 2));
