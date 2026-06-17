# Generated from SMILE_Specific.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .SMILE_SpecificParser import SMILE_SpecificParser
else:
    from SMILE_SpecificParser import SMILE_SpecificParser

# This class defines a complete generic visitor for a parse tree produced by SMILE_SpecificParser.

class SMILE_SpecificVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by SMILE_SpecificParser#migration.
    def visitMigration(self, ctx:SMILE_SpecificParser.MigrationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#header.
    def visitHeader(self, ctx:SMILE_SpecificParser.HeaderContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#migrationDecl.
    def visitMigrationDecl(self, ctx:SMILE_SpecificParser.MigrationDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#evolutionDecl.
    def visitEvolutionDecl(self, ctx:SMILE_SpecificParser.EvolutionDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#fromToDecl.
    def visitFromToDecl(self, ctx:SMILE_SpecificParser.FromToDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#usingDecl.
    def visitUsingDecl(self, ctx:SMILE_SpecificParser.UsingDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#databaseType.
    def visitDatabaseType(self, ctx:SMILE_SpecificParser.DatabaseTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#version.
    def visitVersion(self, ctx:SMILE_SpecificParser.VersionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#operation.
    def visitOperation(self, ctx:SMILE_SpecificParser.OperationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#add_property.
    def visitAdd_property(self, ctx:SMILE_SpecificParser.Add_propertyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#propertyClause.
    def visitPropertyClause(self, ctx:SMILE_SpecificParser.PropertyClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#withTypeClause.
    def visitWithTypeClause(self, ctx:SMILE_SpecificParser.WithTypeClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#withDefaultClause.
    def visitWithDefaultClause(self, ctx:SMILE_SpecificParser.WithDefaultClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#notNullClause.
    def visitNotNullClause(self, ctx:SMILE_SpecificParser.NotNullClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#add_foreign_key.
    def visitAdd_foreign_key(self, ctx:SMILE_SpecificParser.Add_foreign_keyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#constraintClause.
    def visitConstraintClause(self, ctx:SMILE_SpecificParser.ConstraintClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#add_embedded.
    def visitAdd_embedded(self, ctx:SMILE_SpecificParser.Add_embeddedContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#embeddedClause.
    def visitEmbeddedClause(self, ctx:SMILE_SpecificParser.EmbeddedClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#withStructureClause.
    def visitWithStructureClause(self, ctx:SMILE_SpecificParser.WithStructureClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#add_entity.
    def visitAdd_entity(self, ctx:SMILE_SpecificParser.Add_entityContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#entityClause.
    def visitEntityClause(self, ctx:SMILE_SpecificParser.EntityClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#withKeyClause.
    def visitWithKeyClause(self, ctx:SMILE_SpecificParser.WithKeyClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#add_primary_key.
    def visitAdd_primary_key(self, ctx:SMILE_SpecificParser.Add_primary_keyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#add_unique_key.
    def visitAdd_unique_key(self, ctx:SMILE_SpecificParser.Add_unique_keyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#add_partition_key.
    def visitAdd_partition_key(self, ctx:SMILE_SpecificParser.Add_partition_keyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#add_clustering_key.
    def visitAdd_clustering_key(self, ctx:SMILE_SpecificParser.Add_clustering_keyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#add_label.
    def visitAdd_label(self, ctx:SMILE_SpecificParser.Add_labelContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#keyColumns.
    def visitKeyColumns(self, ctx:SMILE_SpecificParser.KeyColumnsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#keyClause.
    def visitKeyClause(self, ctx:SMILE_SpecificParser.KeyClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#referencesClause.
    def visitReferencesClause(self, ctx:SMILE_SpecificParser.ReferencesClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#withColumnsClause.
    def visitWithColumnsClause(self, ctx:SMILE_SpecificParser.WithColumnsClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#delete_property.
    def visitDelete_property(self, ctx:SMILE_SpecificParser.Delete_propertyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#delete_foreign_key.
    def visitDelete_foreign_key(self, ctx:SMILE_SpecificParser.Delete_foreign_keyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#delete_embedded.
    def visitDelete_embedded(self, ctx:SMILE_SpecificParser.Delete_embeddedContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#delete_entity.
    def visitDelete_entity(self, ctx:SMILE_SpecificParser.Delete_entityContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#delete_primary_key.
    def visitDelete_primary_key(self, ctx:SMILE_SpecificParser.Delete_primary_keyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#delete_unique_key.
    def visitDelete_unique_key(self, ctx:SMILE_SpecificParser.Delete_unique_keyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#delete_partition_key.
    def visitDelete_partition_key(self, ctx:SMILE_SpecificParser.Delete_partition_keyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#delete_clustering_key.
    def visitDelete_clustering_key(self, ctx:SMILE_SpecificParser.Delete_clustering_keyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#delete_label.
    def visitDelete_label(self, ctx:SMILE_SpecificParser.Delete_labelContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#rename_property.
    def visitRename_property(self, ctx:SMILE_SpecificParser.Rename_propertyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#rename_entity.
    def visitRename_entity(self, ctx:SMILE_SpecificParser.Rename_entityContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#flatten.
    def visitFlatten(self, ctx:SMILE_SpecificParser.FlattenContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#unflatten.
    def visitUnflatten(self, ctx:SMILE_SpecificParser.UnflattenContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#unnest.
    def visitUnnest(self, ctx:SMILE_SpecificParser.UnnestContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#unnestCarryList.
    def visitUnnestCarryList(self, ctx:SMILE_SpecificParser.UnnestCarryListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#unnestCarryField.
    def visitUnnestCarryField(self, ctx:SMILE_SpecificParser.UnnestCarryFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#unnestFieldList.
    def visitUnnestFieldList(self, ctx:SMILE_SpecificParser.UnnestFieldListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#SimpleField.
    def visitSimpleField(self, ctx:SMILE_SpecificParser.SimpleFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#NestedField.
    def visitNestedField(self, ctx:SMILE_SpecificParser.NestedFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#unwind.
    def visitUnwind(self, ctx:SMILE_SpecificParser.UnwindContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#wind.
    def visitWind(self, ctx:SMILE_SpecificParser.WindContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#nest.
    def visitNest(self, ctx:SMILE_SpecificParser.NestContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#copy_property.
    def visitCopy_property(self, ctx:SMILE_SpecificParser.Copy_propertyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#copy_entity.
    def visitCopy_entity(self, ctx:SMILE_SpecificParser.Copy_entityContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#move_property.
    def visitMove_property(self, ctx:SMILE_SpecificParser.Move_propertyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#merge.
    def visitMerge(self, ctx:SMILE_SpecificParser.MergeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#split.
    def visitSplit(self, ctx:SMILE_SpecificParser.SplitContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#splitPart.
    def visitSplitPart(self, ctx:SMILE_SpecificParser.SplitPartContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#cast_property.
    def visitCast_property(self, ctx:SMILE_SpecificParser.Cast_propertyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#cast_constraint.
    def visitCast_constraint(self, ctx:SMILE_SpecificParser.Cast_constraintContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#add_constraint.
    def visitAdd_constraint(self, ctx:SMILE_SpecificParser.Add_constraintContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#ConstraintBodyReference.
    def visitConstraintBodyReference(self, ctx:SMILE_SpecificParser.ConstraintBodyReferenceContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#ConstraintBodyCheck.
    def visitConstraintBodyCheck(self, ctx:SMILE_SpecificParser.ConstraintBodyCheckContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#ConstraintBodyExistence.
    def visitConstraintBodyExistence(self, ctx:SMILE_SpecificParser.ConstraintBodyExistenceContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#delete_constraint.
    def visitDelete_constraint(self, ctx:SMILE_SpecificParser.Delete_constraintContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#CheckParenExpr.
    def visitCheckParenExpr(self, ctx:SMILE_SpecificParser.CheckParenExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#CheckAtomExpr.
    def visitCheckAtomExpr(self, ctx:SMILE_SpecificParser.CheckAtomExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#CheckAndExpr.
    def visitCheckAndExpr(self, ctx:SMILE_SpecificParser.CheckAndExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#CheckOrExpr.
    def visitCheckOrExpr(self, ctx:SMILE_SpecificParser.CheckOrExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#CheckNotExpr.
    def visitCheckNotExpr(self, ctx:SMILE_SpecificParser.CheckNotExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#CheckRawExpr.
    def visitCheckRawExpr(self, ctx:SMILE_SpecificParser.CheckRawExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#CmpAtom.
    def visitCmpAtom(self, ctx:SMILE_SpecificParser.CmpAtomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#InAtom.
    def visitInAtom(self, ctx:SMILE_SpecificParser.InAtomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#BetweenAtom.
    def visitBetweenAtom(self, ctx:SMILE_SpecificParser.BetweenAtomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#RegexAtom.
    def visitRegexAtom(self, ctx:SMILE_SpecificParser.RegexAtomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#IsNullAtom.
    def visitIsNullAtom(self, ctx:SMILE_SpecificParser.IsNullAtomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#IsNotNullAtom.
    def visitIsNotNullAtom(self, ctx:SMILE_SpecificParser.IsNotNullAtomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#cmpOp.
    def visitCmpOp(self, ctx:SMILE_SpecificParser.CmpOpContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#literalList.
    def visitLiteralList(self, ctx:SMILE_SpecificParser.LiteralListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#cast_entity.
    def visitCast_entity(self, ctx:SMILE_SpecificParser.Cast_entityContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#recard.
    def visitRecard(self, ctx:SMILE_SpecificParser.RecardContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#transform.
    def visitTransform(self, ctx:SMILE_SpecificParser.TransformContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#TransformToRelationship.
    def visitTransformToRelationship(self, ctx:SMILE_SpecificParser.TransformToRelationshipContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#TransformToEntity.
    def visitTransformToEntity(self, ctx:SMILE_SpecificParser.TransformToEntityContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#withCardinalityClause.
    def visitWithCardinalityClause(self, ctx:SMILE_SpecificParser.WithCardinalityClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#usingKeyClause.
    def visitUsingKeyClause(self, ctx:SMILE_SpecificParser.UsingKeyClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#whereClause.
    def visitWhereClause(self, ctx:SMILE_SpecificParser.WhereClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#withPropertiesClause.
    def visitWithPropertiesClause(self, ctx:SMILE_SpecificParser.WithPropertiesClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#propertyDefList.
    def visitPropertyDefList(self, ctx:SMILE_SpecificParser.PropertyDefListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#propertyDef.
    def visitPropertyDef(self, ctx:SMILE_SpecificParser.PropertyDefContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#identifierList.
    def visitIdentifierList(self, ctx:SMILE_SpecificParser.IdentifierListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#cardinalityType.
    def visitCardinalityType(self, ctx:SMILE_SpecificParser.CardinalityTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#constraintKeyType.
    def visitConstraintKeyType(self, ctx:SMILE_SpecificParser.ConstraintKeyTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#dataType.
    def visitDataType(self, ctx:SMILE_SpecificParser.DataTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#qualifiedName.
    def visitQualifiedName(self, ctx:SMILE_SpecificParser.QualifiedNameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#pathSegment.
    def visitPathSegment(self, ctx:SMILE_SpecificParser.PathSegmentContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#identifier.
    def visitIdentifier(self, ctx:SMILE_SpecificParser.IdentifierContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#condition.
    def visitCondition(self, ctx:SMILE_SpecificParser.ConditionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#equalityOnlyCondition.
    def visitEqualityOnlyCondition(self, ctx:SMILE_SpecificParser.EqualityOnlyConditionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#equalityCondition.
    def visitEqualityCondition(self, ctx:SMILE_SpecificParser.EqualityConditionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#edgeCondition.
    def visitEdgeCondition(self, ctx:SMILE_SpecificParser.EdgeConditionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SMILE_SpecificParser#literal.
    def visitLiteral(self, ctx:SMILE_SpecificParser.LiteralContext):
        return self.visitChildren(ctx)



del SMILE_SpecificParser